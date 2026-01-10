import socket

# הגדרות
UDP_PORT = 13117


def sniff_packets():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # מאפשר להאזין גם אם תוכנות אחרות מאזינות (חשוב לווינדוס)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    s.bind(("", UDP_PORT))

    print(f"👀 Sniffer started listening on port {UDP_PORT}...")

    while True:
        # קבלת נתונים גולמיים
        data, addr = s.recvfrom(1024)

        # הדפסה של המידע הגולמי (בבתים) ומאיפה הוא הגיע
        print(f"📦 Received {len(data)} bytes from {addr}: {data}")


if __name__ == "__main__":
    sniff_packets()