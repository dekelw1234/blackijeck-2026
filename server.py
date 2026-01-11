import socket
import time
import threading
import protocol
from game_logic import BlackjackGame
from concurrent.futures import ThreadPoolExecutor
import logging

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(threadName)-12s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- Network Constants ---
UDP_DEST_PORT = 13122
BROADCAST_IP = '<broadcast>'
TCP_PORT = 0
CLIENT_TIMEOUT = 60
MAX_CONCURRENT_CLIENTS = 10  # Thread pool size

# --- Global Statistics (Thread-Safe) ---
active_players = 0
active_players_lock = threading.Lock()

# --- Thread Pool ---
thread_pool = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_CLIENTS, thread_name_prefix="ClientHandler")


def get_local_ip():
    """
    Attempts to find the actual local IP address of the machine.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Create UDP socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        # Get the local IP address that the socket is using.
        ip = s.getsockname()[0]
        # Close the socket.
        s.close()
    except Exception:
        # If something goes wrong (for example: no internet connection),
        # return a default IP address as a fallback.
        s.close()
        ip = "26.113.0.164"

    # Return the detected local IP address.
    return ip

def broadcast_offers(server_tcp_port):
    """
    Broadcasts UDP offers every 1 second.
    Thread-safe logging via logger.
    """
    # Create a UDP socket for sending broadcast messages.
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Allows the socket to send packets to the broadcast address.
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    try:
        while True:
            # The packet contains the TCP port and the server name.
            packet = protocol.pack_offer(server_tcp_port, "Dekel-Sagi-Server")
            # Send the offer packet to all devices in the local network
            # using the broadcast IP and the predefined UDP port.
            udp_socket.sendto(packet, (BROADCAST_IP, UDP_DEST_PORT))
            time.sleep(1)
    except Exception as e:
        logger.error(f"Error in broadcast thread: {e}")
    finally:
        udp_socket.close()


def send_game_packet(sock, result, card):
    """
    Helper function to pack and send a game payload message.
    """
    rank, suit = card
    packet = protocol.pack_server_payload(result, rank, suit)
    sock.sendall(packet)


def calculate_points_safe(cards):
    """
    Internal helper to calculate hand value safely.
    Prevents logic errors if the external game library behaves unexpectedly.
    """
    total = 0
    aces = 0
    for card in cards:
        rank = card[0]
        if rank == 1:  # Ace
            aces += 1
            total += 11
        elif rank >= 10:  # Face cards
            total += 10
        else:
            total += rank

    # Handle Aces
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total



def drain_socket(sock):
    """
    Clears any pending data in the socket buffer.
    Prevents 'Ghost Commands' from previous rounds.
    """
    try:
        sock.setblocking(False)
        while sock.recv(1024):
            pass
    except:
        pass
    finally:
        sock.setblocking(True)


def play_one_round(client_socket, game_num, client_name, client_addr):

    drain_socket(client_socket)
    time.sleep(0.8)

    game = BlackjackGame()
    player_cards = []
    dealer_cards = []

    log_prefix = f"[{client_name} | {client_addr[0]}:{client_addr[1]}]"
    logger.info(f"{log_prefix} Starting Round {game_num}")

    # 1. Initial Deal
    player_cards.append(game.draw_card())
    player_cards.append(game.draw_card())
    dealer_cards.append(game.draw_card())
    dealer_cards.append(game.draw_card())

    send_game_packet(client_socket, 0, player_cards[0])
    time.sleep(0.2)
    send_game_packet(client_socket, 0, player_cards[1])
    time.sleep(0.2)
    send_game_packet(client_socket, 0, dealer_cards[0]) # revel only the first card
    time.sleep(0.2)

    # 2. Player Turn
    while True:
        player_sum = calculate_points_safe(player_cards)

        if player_sum >= 21:
            if player_sum > 21:
                logger.info(f"{log_prefix} Player busted with {player_sum}!")
                send_game_packet(client_socket, 2, None)  # Player bust
                logger.info(f"{log_prefix} Round {game_num} finished. Result code: 2")
                return
            else:  # player_sum == 21
                logger.info(f"{log_prefix} Player has 21, auto-stand.")
                break

        try:
            client_socket.settimeout(CLIENT_TIMEOUT)
            data = client_socket.recv(1024)
            client_socket.settimeout(None)

            if not data: raise Exception("Client disconnected")

            decision = protocol.unpack_client_payload(data)

            if decision == "Hittt":
                new_card = game.draw_card()
                player_cards.append(new_card)
                new_sum = calculate_points_safe(player_cards)

                if new_sum > 21:
                    send_game_packet(client_socket, 0, new_card)  # שלח את הקלף
                    time.sleep(0.3)
                    send_game_packet(client_socket, 2, None)
                    logger.info(f"{log_prefix} Player busted with {new_sum}!")
                    logger.info(f"{log_prefix} Round {game_num} finished. Result code: 2")
                    return
                else:
                    send_game_packet(client_socket, 0, new_card)
                    time.sleep(0.2)

            elif decision == "Stand":
                logger.info(f"{log_prefix} Player chose to Stand with {player_sum}.")
                break
            else:
                logger.debug(f"{log_prefix} Received invalid packet/garbage. Ignoring.")
                continue

        except socket.timeout:
            logger.warning(f"{log_prefix} Timed out.")
            raise Exception("Game Timeout")
        except Exception as e:
            logger.error(f"{log_prefix} Connection error: {e}")
            raise e

    # 3. Dealer Turn
    time.sleep(0.5)
    send_game_packet(client_socket, 0, dealer_cards[1]) # revel the second dealer card
    time.sleep(0.5)

    dealer_sum = calculate_points_safe(dealer_cards)
    logger.debug(f"{log_prefix} Initial Dealer Hand: {dealer_cards} (Sum: {dealer_sum})")

    while dealer_sum<17:
        new_card = game.draw_card()
        dealer_cards.append(new_card)
        dealer_sum = calculate_points_safe(dealer_cards)

        logger.debug(f"{log_prefix} Dealer drew {new_card}. New Sum: {dealer_sum}")

        send_game_packet(client_socket, 0, new_card)  # send the new card to client
        time.sleep(0.5)

    logger.info(f"{log_prefix} Dealer stands with {dealer_sum}")

    # 4. Result Logic
    time.sleep(0.5)

    player_final = calculate_points_safe(player_cards)
    dealer_final = dealer_sum

    logger.debug(f"{log_prefix} FINAL -> Player: {player_final}, Dealer: {dealer_final}")

    if dealer_final > 21:
        winner = 3  # Dealer bust - Player wins
        logger.info(f"{log_prefix} Dealer busted! Player wins.")
    elif player_final > dealer_final:
        winner = 3  # Player wins
        logger.info(f"{log_prefix} Player wins ({player_final} > {dealer_final})")
    elif dealer_final > player_final:
        winner = 2  # Dealer wins
        logger.info(f"{log_prefix} Dealer wins ({dealer_final} > {player_final})")
    else:
        winner = 1  # Tie
        logger.info(f"{log_prefix} Tie ({player_final} == {dealer_final})")

    send_game_packet(client_socket, winner, None)
    logger.info(f"{log_prefix} Round {game_num} finished. Result code: {winner}")


def handle_client(client_socket, client_addr):
    """
    Handles a single client connection.
    Updates global player statistics (thread-safe with lock).
    Each client runs in its own thread from the thread pool.
    """
    global active_players

    # Update stats safely (Thread Safe)
    with active_players_lock:
        active_players += 1
        current_players = active_players

    logger.info(f"New Connection: {client_addr[0]}:{client_addr[1]} | Total Players: {current_players}")

    try:
        # Handshake
        client_socket.settimeout(CLIENT_TIMEOUT)
        request_data = client_socket.recv(1024)
        client_socket.settimeout(None)

        valid_request = protocol.unpack_request(request_data)
        if not valid_request:
            logger.warning(f"Invalid request from {client_addr}")
            return

        num_rounds, client_name = valid_request
        logger.info(f"Player '{client_name}' ({client_addr[0]}) wants {num_rounds} rounds")

        # Game Loop
        for i in range(num_rounds):
            play_one_round(client_socket, i + 1, client_name, client_addr)
            time.sleep(1.5)

        logger.info(f"Finished serving '{client_name}' at {client_addr[0]}")
        time.sleep(2.0)

    except Exception as e:
        logger.error(f"Error serving {client_addr}: {e}")
    finally:
        # Update stats safely on exit
        with active_players_lock:
            active_players -= 1
            remaining = active_players

        logger.info(f"Disconnected: {client_addr[0]}:{client_addr[1]} | Total Players: {remaining}")
        client_socket.close()


def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('0.0.0.0', TCP_PORT))
    server_tcp_port = server_socket.getsockname()[1]
    server_socket.listen()

    logger.info(f"Server started on IP {get_local_ip()}")
    logger.info(f"Listening on TCP port {server_tcp_port}")
    logger.info(f"Thread pool max workers: {MAX_CONCURRENT_CLIENTS}")
    logger.info("Waiting for clients...")

    server_socket.settimeout(1.0)

    broadcast_thread = threading.Thread(target=broadcast_offers, args=(server_tcp_port,), daemon=True, name="BroadcastThread")
    broadcast_thread.daemon = True
    broadcast_thread.start()

    try:
        while True:
            try:
                client_sock, client_addr = server_socket.accept()
                # Submit client handling to thread pool instead of creating new threads
                thread_pool.submit(handle_client, client_sock, client_addr)

            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"Server error: {e}")
                break
    finally:
        logger.info("Shutting down thread pool...")
        thread_pool.shutdown(wait=True)
        server_socket.close()


if __name__ == "__main__":
    start_server()