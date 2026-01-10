import socket
import time
import threading
import protocol
from game_logic import BlackjackGame

# --- Network Constants ---
UDP_DEST_PORT = 13122
BROADCAST_IP = '<broadcast>'
TCP_PORT = 0
CLIENT_TIMEOUT = 60

# --- Global Statistics ---
active_players = 0  # Counter for connected clients
active_players_lock = threading.Lock()  # Thread-safety for the counter


def get_local_ip():
    """
    Attempts to find the actual local IP address of the machine.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def broadcast_offers(server_tcp_port):
    """
    Broadcasts UDP offers every 1 second.
    """
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    try:
        while True:
            packet = protocol.pack_offer(server_tcp_port, "Dekel-Sagi-Server")
            udp_socket.sendto(packet, (BROADCAST_IP, UDP_DEST_PORT))
            time.sleep(1)
    except Exception as e:
        print(f"Error in broadcast thread: {e}")
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
    print(f"{log_prefix} Starting Round {game_num}")

    # 1. Initial Deal
    player_cards.append(game.draw_card())
    player_cards.append(game.draw_card())
    dealer_cards.append(game.draw_card())
    dealer_cards.append(game.draw_card())

    send_game_packet(client_socket, 0, player_cards[0])
    time.sleep(0.2)
    send_game_packet(client_socket, 0, player_cards[1])
    time.sleep(0.2)
    send_game_packet(client_socket, 0, dealer_cards[0])
    time.sleep(0.2)

    # 2. Player Turn
    player_bust = False
    while True:
        if calculate_points_safe(player_cards) >= 21:
            break

        try:
            client_socket.settimeout(CLIENT_TIMEOUT)
            data = client_socket.recv(1024)
            client_socket.settimeout(None)

            if not data: raise Exception("Client disconnected")

            decision = protocol.unpack_client_payload(data)

            # רק אם הפקודה היא בפירוש "Stand" עוצרים.
            if decision == "Hittt":
                new_card = game.draw_card()
                player_cards.append(new_card)
                player_sum = calculate_points_safe(player_cards)

                if player_sum > 21:
                    send_game_packet(client_socket, 2, new_card)
                    print(f"{log_prefix} Player busted with {player_sum}!")
                    print(f"{log_prefix} Round {game_num} finished. Result code: 2")
                    return
                else:
                    send_game_packet(client_socket, 0, new_card)

            elif decision == "Stand":
                print(f"{log_prefix} Player chose to Stand.")
                break

            else:
                print(f"{log_prefix} Received invalid packet/garbage. Ignoring.")
                continue

        except socket.timeout:
            print(f"{log_prefix} Timed out.")
            raise Exception("Game Timeout")
        except Exception as e:
            print(f"{log_prefix} Connection error: {e}")
            raise e

    # 3. Dealer Turn
    dealer_sum = calculate_points_safe(dealer_cards)
    print(f"DEBUG: Initial Dealer Hand: {dealer_cards} (Sum: {dealer_sum})")

    if dealer_sum < 17:
        send_game_packet(client_socket, 0, dealer_cards[1])  # Reveal

        while dealer_sum < 17:
            time.sleep(0.5)
            new_card = game.draw_card()
            dealer_cards.append(new_card)
            dealer_sum = calculate_points_safe(dealer_cards)

            print(f"DEBUG: Dealer drew {new_card}. New Sum: {dealer_sum}")

            if dealer_sum < 17:
                send_game_packet(client_socket, 0, new_card)
    else:
        print(f"{log_prefix} Dealer stands on initial {dealer_sum}")

    # 4. Result Logic
    p_final = calculate_points_safe(player_cards)
    d_final = calculate_points_safe(dealer_cards)

    print(f"DEBUG FINAL CALC -> Player: {p_final}, Dealer: {d_final}")

    winner = 0
    if d_final > 21:
        winner = 3
    elif p_final > d_final:
        winner = 3
    elif d_final > p_final:
        winner = 2
    else:
        winner = 1

    send_game_packet(client_socket, winner, dealer_cards[-1])
    print(f"{log_prefix} Round {game_num} finished. Result code: {winner}")


def handle_client(client_socket, client_addr):
    """
    Handles a single client connection.
    Updates global player statistics.
    """
    global active_players

    # Update stats safely (Thread Safe)
    with active_players_lock:
        active_players += 1
        current_players = active_players

    print(f"--- New Connection: {client_addr} | Total Players: {current_players} ---")

    try:
        # Handshake
        client_socket.settimeout(CLIENT_TIMEOUT)
        request_data = client_socket.recv(1024)
        client_socket.settimeout(None)

        valid_request = protocol.unpack_request(request_data)
        if not valid_request:
            print(f"Invalid request from {client_addr}")
            return

        num_rounds, client_name = valid_request
        print(f"Player '{client_name}' ({client_addr[0]}) wants {num_rounds} rounds.")

        # Game Loop
        for i in range(num_rounds):
            play_one_round(client_socket, i + 1, client_name, client_addr)
            time.sleep(1.5)


        print(f"Finished serving {client_name} at {client_addr}")
        # Graceful exit wait

        time.sleep(2.0)

    except Exception as e:
        print(f"Error serving {client_addr}: {e}")
    finally:
        # Update stats safely on exit
        with active_players_lock:
            active_players -= 1
            remaining = active_players

        print(f"--- Disconnected: {client_addr} | Total Players: {remaining} ---")
        client_socket.close()


def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('0.0.0.0', TCP_PORT))
    server_tcp_port = server_socket.getsockname()[1]
    server_socket.listen()

    print(f"Server started on IP {get_local_ip()}")
    print(f"Listening on TCP port {server_tcp_port}")
    print("Waiting for clients...")

    server_socket.settimeout(1.0)

    broadcast_thread = threading.Thread(target=broadcast_offers, args=(server_tcp_port,))
    broadcast_thread.daemon = True
    broadcast_thread.start()

    while True:
        try:
            client_sock, client_addr = server_socket.accept()
            client_thread = threading.Thread(target=handle_client, args=(client_sock, client_addr))
            client_thread.start()

        except socket.timeout:
            continue
        except Exception as e:
            print(f"Server error: {e}")
            break

    server_socket.close()


if __name__ == "__main__":
    start_server()