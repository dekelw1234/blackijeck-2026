import socket
import threading
import time
import random
import Protocols_and_Logics.protocol

UDP_PORT = 13122
NUM_BOTS = 50
PACKET_SIZE = 9   # size of server payload packet


# ------------------------
# Helpers
# ------------------------

def recv_all(sock, n):
    """Receive exactly n bytes from TCP socket."""
    data = b''
    while len(data) < n:
        try:
            part = sock.recv(n - len(data))
            if not part:
                return None
            data += part
        except:
            return None
    return data


def listen_for_offer():
    """Listen for a single UDP offer and return (server_ip, server_tcp_port)."""
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        try:
            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except AttributeError:
            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        udp_socket.bind(("", UDP_PORT))
        udp_socket.settimeout(15)

        data, addr = udp_socket.recvfrom(1024)
        server_ip = addr[0]

        result = protocol.unpack_offer(data)
        if not result:
            return None, None

        server_tcp_port, _ = result
        return server_ip, server_tcp_port

    except socket.timeout:
        return None, None
    finally:
        udp_socket.close()


# ------------------------
# Bot logic (state machine)
# ------------------------

def run_bot(bot_id):
    tcp_socket = None

    try:
        # 1. Find server via UDP
        server_ip, server_tcp_port = listen_for_offer()
        if not server_ip:
            print(f"[Bot {bot_id}] No server found.")
            return

        # 2. Connect via TCP
        time.sleep(random.uniform(0.05, 0.3))  # small jitter
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket.connect((server_ip, server_tcp_port))

        # 3. Send request
        rounds = random.randint(1, 3)
        req = protocol.pack_request(rounds, f"Bot-{bot_id}")
        tcp_socket.sendall(req)

        print(f"[Bot {bot_id}] Connected. Playing {rounds} rounds.")

        # ------------------------
        # State variables
        # ------------------------
        cards_received = 0   # how many cards received in current round
        my_turn = True      # whether bot is still allowed to act

        # ------------------------
        # Game loop
        # ------------------------
        while True:
            packet = recv_all(tcp_socket, PACKET_SIZE)
            if not packet:
                break

            parsed = protocol.unpack_server_payload(packet)
            if not parsed:
                continue

            result, rank, suit = parsed

            # ------------------------
            # Round finished
            # ------------------------
            if result != 0:
                # Reset state for next round
                cards_received = 0
                my_turn = True
                continue

            # ------------------------
            # Card received during active round
            # ------------------------
            cards_received += 1

            # Wait until:
            # 2 player cards + 1 dealer card
            if my_turn and cards_received >= 3:
                # Decide action
                # Example strategy: 70% Hit, 30% Stand
                action = "Hittt" if random.random() < 0.7 else "Stand"

                try:
                    tcp_socket.sendall(protocol.pack_client_payload(action))
                except:
                    break

                # If bot stands, it should NOT send any more actions
                if action == "Stand":
                    my_turn = False

    except Exception as e:
        # Ignore normal disconnect errors
        if "WinError 10054" not in str(e) and "WinError 10053" not in str(e):
            print(f"[Bot {bot_id}] Error: {e}")

    finally:
        if tcp_socket:
            try:
                tcp_socket.close()
            except:
                pass
        print(f"[Bot {bot_id}] Finished.")


# ------------------------
# Stress test runner
# ------------------------

def start_stress_test():
    print(f"--- Starting Stress Test with {NUM_BOTS} bots ---")
    print("Waiting for UDP Broadcasts...")

    threads = []

    for i in range(NUM_BOTS):
        t = threading.Thread(target=run_bot, args=(i + 1,), name=f"BotThread-{i+1}")
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    print("--- Stress Test Finished ---")


if __name__ == "__main__":
    start_stress_test()
