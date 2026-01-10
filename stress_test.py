import socket
import threading
import time
import random
import protocol


UDP_PORT = 13122
NUM_BOTS = 10


def run_bot(bot_id):
    tcp_socket = None
    try:
        # 1. האזנה ל-UDP כדי למצוא את השרת
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except AttributeError:
            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        udp_socket.bind(("", UDP_PORT))
        udp_socket.settimeout(15)  # ניתן להם קצת זמן למצוא את השרת

        try:
            data, addr = udp_socket.recvfrom(1024)
            server_ip = addr[0]

            # --- התיקון כאן: הסדר הנכון של המשתנים ---
            server_tcp_port, _ = protocol.unpack_offer(data)

        except socket.timeout:
            print(f"[Bot {bot_id}] No UDP offer found.")
            return
        finally:
            udp_socket.close()

        # 2. התחברות לשרת (TCP)
        # השהיה אקראית קטנה כדי לא להפיל את השרת בבת אחת
        time.sleep(random.uniform(0.1, 0.5))

        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket.connect((server_ip, server_tcp_port))

        # 3. בקשת משחק (1-3 סיבובים רנדומלית)
        rounds = random.randint(1, 3)
        req = protocol.pack_request(rounds, f"Bot-{bot_id}")
        tcp_socket.sendall(req)

        print(f"[Bot {bot_id}] Connected! Playing {rounds} rounds...")

        # 4. לולאת המשחק
        while True:
            packet = tcp_socket.recv(1024)
            if not packet: break

            parsed = protocol.unpack_server_payload(packet)
            if not parsed: continue

            result, rank, suit = parsed

            # אם הסיבוב נגמר (ניצחון/הפסד/תיקו)
            if result != 0:
                # אם הבוט הפסיד/ניצח בסיבוב האחרון שלו, השרת יסגור חיבור בקרוב
                continue

                # אם המשחק פעיל, צריך להחליט (Hit/Stand)
            # החלטה רנדומלית מהירה
            action = random.choice(["Hittt", "Stand"])

            try:
                tcp_socket.sendall(protocol.pack_client_payload(action))
            except:
                break

    except Exception as e:
        # התעלמות משגיאות ניתוק רגילות בסוף המשחק
        if "WinError 10054" not in str(e) and "WinError 10053" not in str(e):
            print(f"[Bot {bot_id}] Error: {e}")
    finally:
        if tcp_socket:
            tcp_socket.close()
        print(f"[Bot {bot_id}] Finished.")


def start_stress_test():
    print(f"--- Starting Stress Test with {NUM_BOTS} bots ---")
    print("Waiting for UDP Broadcasts...")

    threads = []
    for i in range(NUM_BOTS):
        t = threading.Thread(target=run_bot, args=(i + 1,))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    print("--- Stress Test Finished ---")


if __name__ == "__main__":
    start_stress_test()