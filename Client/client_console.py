import socket
import Protocols_and_Logics.protocol
import os
import time

# --- Network Constants ---
UDP_PORT = 13122
BUFFER_SIZE = 1024

cow = [
    r"      ^__^",
    r"      (oo)\_______",
    r"      (__)\       )\/\ ",
    r"          ||----w |",
    r"          ||     ||",
]

# --- Colors for Terminal ---
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"


# Enable colors for Windows legacy cmd
os.system('color')


def card_to_string(rank, suit):
    """
    Converts internal card representation to a readable colored string.
    Hearts/Diamonds -> Red
    Clubs/Spades -> Cyan
    """
    suits = ['♥', '♦', '♣', '♠']
    ranks = {1: 'A', 11: 'J', 12: 'Q', 13: 'K'}
    r_str = ranks.get(rank, str(rank))

    card_text = f"{r_str}{suits[suit]}"

    # Suit 0 (Hearts) and 1 (Diamonds) are Red
    if suit in [0, 1]:
        return f"{Colors.RED}{card_text}{Colors.RESET}"
    # Suit 2 (Clubs) and 3 (Spades) are Cyan
    else:
        return f"{Colors.CYAN}{card_text}{Colors.RESET}"


def calculate_hand(ranks):
    """
    Calculates the sum of the hand based on ranks list.
    """
    total = 0
    aces = 0

    for r in ranks:
        if r == 1:  # Ace
            aces += 1
            total += 11
        elif r >= 10:  # Face cards (10, J, Q, K)
            total += 10
        else:
            total += r

    # Handle Aces
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1

    return total


def print_end_game_art(win_rate):
    """
    Prints ASCII art based on the win rate.
    """
    if win_rate < 50:
        # Donkey Art
        print(f"{Colors.RED}")
        print(r"      ^__^")
        print(r"      (oo)\_______")
        print(r"      (__)\       )\/\ ")
        print(r"          ||----w |")
        print(r"          ||     ||")
        print(f"{Colors.BOLD} The House Always Wins! Don't be a donkey...{Colors.RESET}")
    else:
        # Trophy Art
        print(f"{Colors.GREEN}")
        print(r"             ___________")
        print(r"            '._==_==_=_.'")
        print(r"            .-\:      /-.")
        print(r"           | (|:.     |) |")
        print(r"            '-|:.     |-'")
        print(r"              \::.    /")
        print(r"               '::. .'")
        print(r"                 ) (")
        print(r"               _.' '._")
        print(r"              `-------`")
        print(f"{Colors.BOLD}     Winner Winner Chicken Dinner!{Colors.RESET}")


def listen_for_offers():
    """
    Listens for UDP broadcast offers.
    """
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except AttributeError:
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    udp_socket.bind(("", UDP_PORT))
    print(f"{Colors.YELLOW}Client started, listening for offer requests...{Colors.RESET}")

    while True:
        data, addr = udp_socket.recvfrom(BUFFER_SIZE)
        server_ip = addr[0]
        result = protocol.unpack_offer(data)

        if result:
            server_tcp_port, server_name = result
            print(f"Received offer from {Colors.BOLD}{server_name}{Colors.RESET} at {server_ip}")
            udp_socket.close()
            return server_ip, server_tcp_port


def connect_to_server(server_ip, server_port):
    """
    Connects via TCP and sends initial request.
    """
    try:
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print(f"Connecting to server at {server_ip}:{server_port}...")
        tcp_socket.connect((server_ip, server_port))

        team_name = "Team-Dekel-And-Sagi"
        try:
            while True:
                num_rounds = input(f"{Colors.BOLD}How many rounds would you like to play? {Colors.RESET}")
                if num_rounds.strip().isdigit() and int(num_rounds) > 0:
                    num_rounds = int(num_rounds)
                    break
                else:
                    print(f"{Colors.RED}Please enter a valid positive integer for rounds.{Colors.RESET}")
        except ValueError:
            num_rounds = 1

        request_packet = protocol.pack_request(num_rounds, team_name)
        tcp_socket.sendall(request_packet)

        return tcp_socket, num_rounds

    except Exception as e:
        print(f"{Colors.RED}Failed to connect: {e}{Colors.RESET}")
        return None, 0


def recv_all(sock, n):
    """
    Helper function to receive exactly n bytes.
    Prevents sticky packet issues within a round.
    """
    data = b''
    while len(data) < n:
        try:
            packet = sock.recv(n - len(data))
            if not packet:
                return None
            data += packet
        except:
            return None
    return data


def drain_socket(sock):
    """
    Clears any pending data in the socket buffer.
    Helps prevent ghost packets from previous rounds.
    """
    sock.setblocking(False)
    try:
        while sock.recv(1024): pass
    except: pass
    sock.setblocking(True)


def start_client():
    server_ip, server_port = listen_for_offers()
    tcp_socket, num_rounds = connect_to_server(server_ip, server_port)

    if not tcp_socket:
        return

    print(f"{Colors.GREEN}Connected successfully! Waiting for game to start...{Colors.RESET}")
    wins = 0
    rounds_played = 0

    try:
        while rounds_played < num_rounds:
            drain_socket(tcp_socket)

            print(f"\n{Colors.BLUE}{Colors.BOLD}--- Round {rounds_played + 1} of {num_rounds} ---{Colors.RESET}")
            print(f"--- Starting a New Round ---")
            time.sleep(0.4)
            print(f"Preparing the table...")
            time.sleep(0.4)
            print(f"Dealer shuffled the deck.")

            my_cards_str = []
            my_cards_ranks = []
            dealer_cards_str = []
            dealer_cards_ranks = []
            my_turn = True
            cards_received_counter = 0

            while True:
                packet = recv_all(tcp_socket, 9)

                # Graceful disconnect
                if not packet:
                    print(f"{Colors.RED}Server disconnected.{Colors.RESET}")
                    return  # Goes to finally block

                parsed_packet = protocol.unpack_server_payload(packet)
                if not parsed_packet: continue

                result, rank, suit = parsed_packet
                card_str = card_to_string(rank, suit)

                # --- Round End / Game Over ---
                if result != 0:
                    if result == 3:  # Win
                        wins += 1
                        result_msg = f"{Colors.GREEN}{Colors.BOLD}You Won!{Colors.RESET}"
                    elif result == 2:  # Loss
                        result_msg = f"{Colors.RED}{Colors.BOLD}You Lost!{Colors.RESET}"
                    else:  # Tie
                        result_msg = f"{Colors.YELLOW}{Colors.BOLD}It's a Tie!{Colors.RESET}"

                    if result == 2 and my_turn:
                        my_cards_str.append(card_str)
                        my_cards_ranks.append(rank)
                        print(f"You drew: {card_str} {Colors.RED}(Busted!){Colors.RESET}")
                    else:
                        dealer_cards_str.append(card_str)
                        dealer_cards_ranks.append(rank)
                        print(f"Dealer's last card: {card_str}")
                        print(f"Dealer's Hand: {', '.join(dealer_cards_str)}")

                    # --- Final Summary ---
                    my_sum = calculate_hand(my_cards_ranks)
                    dealer_sum = calculate_hand(dealer_cards_ranks)

                    print("-" * 30)
                    print(f"Your Hand:    {', '.join(my_cards_str)} (Sum: {my_sum})")
                    print(f"Dealer's Hand: {', '.join(dealer_cards_str)} (Sum: {dealer_sum})")
                    print("-" * 30)
                    print(f"Round Result: {result_msg}")

                    rounds_played += 1
                    break

                    # --- Active Game ---
                cards_received_counter += 1
                if my_turn:
                    if cards_received_counter <= 2:
                        my_cards_str.append(card_str)
                        my_cards_ranks.append(rank)
                        if len(my_cards_str) == 2:
                            my_sum = calculate_hand(my_cards_ranks)
                            print(f"Your Hand: {', '.join(my_cards_str)} (Sum: {my_sum})")
                    elif cards_received_counter == 3:
                        dealer_cards_str.append(card_str)
                        dealer_cards_ranks.append(rank)
                        d_sum = calculate_hand(dealer_cards_ranks)
                        print(f"Dealer shows: {', '.join(dealer_cards_str)} (Visible Sum: {d_sum})")
                    else:
                        my_cards_str.append(card_str)
                        my_cards_ranks.append(rank)
                        my_sum = calculate_hand(my_cards_ranks)
                        print(f"You drew: {card_str} -> Hand: {', '.join(my_cards_str)} (Sum: {my_sum})")
                else:
                    dealer_cards_str.append(card_str)
                    dealer_cards_ranks.append(rank)
                    if len(dealer_cards_str) == 2:
                        print(f"Dealer reveal his second card: {card_str} (Sum: {calculate_hand(dealer_cards_ranks)})")
                    else:
                        print(f"Dealer drew: {card_str}")
                    print(f"Dealer's Hand: {', '.join(dealer_cards_str)}")

                if my_turn and cards_received_counter >= 3:
                    while True:
                        msg = f"Choose action: {Colors.BOLD}[h]{Colors.RESET}it or {Colors.BOLD}[s]{Colors.RESET}tand? "
                        action = input(msg).strip().lower()
                        if action == 'h':
                            tcp_socket.sendall(protocol.pack_client_payload("Hittt"))
                            break
                        elif action == 's':
                            tcp_socket.sendall(protocol.pack_client_payload("Stand"))
                            my_turn = False
                            print("Standing. Watching dealer...")
                            break
                        else:
                            print("Invalid input! Please enter 'h' or 's'.")

    except Exception as e:
        print(f"{Colors.RED}Game error: {e}{Colors.RESET}")
    finally:
        # --- Final Statistics & Art ---
        print("\n" + "=" * 40)
        if rounds_played > 0:
            win_p = (wins / rounds_played) * 100
            print(
                f"{Colors.BOLD}Finished playing {rounds_played} rounds, win rate: {wins}/{rounds_played} ({win_p:.1f}%){Colors.RESET}")
            print("-" * 40)

            # Print English Art (Donkey or Trophy)
            print_end_game_art(win_p)

        else:
            print("Finished playing 0 rounds.")
        print("=" * 40)

        print("Closing connection.")
        tcp_socket.close()


if __name__ == "__main__":
    while True:
        start_client()
        print(f"{Colors.YELLOW}Looking for a new server in 3 seconds...{Colors.RESET}")
        time.sleep(2)