import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import socket
import threading
import time
import protocol
import struct

# --- Constants ---
UDP_PORT = 13122
BUFFER_SIZE = 1024


# --- Card Display Helper ---
def card_to_display(rank, suit):
    """
    Converts card to readable string with emoji suits
    """
    suits = ['♥', '♦', '♣', '♠']
    ranks = {1: 'A', 11: 'J', 12: 'Q', 13: 'K'}
    r_str = ranks.get(rank, str(rank))
    return f"{r_str}{suits[suit]}"


def calculate_hand(cards):
    """Calculate hand value"""
    total = 0
    aces = 0
    for rank, suit in cards:
        if rank == 1:  # Ace
            aces += 1
            total += 11
        elif rank >= 10:  # Face cards
            total += 10
        else:
            total += rank

    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total


# --- Main GUI Class ---
class BlackjackGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🎲 Blackjack Client")
        self.root.geometry("900x700")
        self.root.configure(bg="#0d5c2d")

        # State
        self.servers = {}
        self.connected = False
        self.game_socket = None
        self.num_rounds = 0
        self.current_round = 0
        self.wins = 0
        self.losses = 0
        self.ties = 0

        # Game state
        self.player_cards = []
        self.dealer_cards = []
        self.my_turn = True
        self.cards_received = 0

        self.create_ui()
        self.start_udp_listener()

    def create_ui(self):
        """Build the interface"""
        # Header
        header_frame = tk.Frame(self.root, bg="#0d5c2d")
        header_frame.pack(pady=10, fill="x")

        title = tk.Label(
            header_frame,
            text="♠️ BLACKJACK ♥️",
            font=("Arial", 36, "bold"),
            bg="#0d5c2d",
            fg="#ffd700"
        )
        title.pack()

        subtitle = tk.Label(
            header_frame,
            text="Network Blackjack Client",
            font=("Arial", 12),
            bg="#0d5c2d",
            fg="#90EE90"
        )
        subtitle.pack()

        # Stats Bar
        self.stats_frame = tk.Frame(self.root, bg="#1a7a42", bd=2, relief="solid")
        self.stats_frame.pack(pady=5, padx=20, fill="x")

        self.stats_label = tk.Label(
            self.stats_frame,
            text="Wins: 0 | Losses: 0 | Ties: 0 | Round: 0/0",
            font=("Arial", 11, "bold"),
            bg="#1a7a42",
            fg="white",
            pady=5
        )
        self.stats_label.pack()

        # Connection Panel
        conn_frame = tk.LabelFrame(
            self.root,
            text="📡 Server Connection",
            font=("Arial", 12, "bold"),
            bg="#1a7a42",
            fg="white",
            bd=2,
            relief="solid"
        )
        conn_frame.pack(pady=10, padx=20, fill="both")

        self.server_list = tk.Listbox(
            conn_frame,
            font=("Courier", 11),
            bg="#2d8f52",
            fg="white",
            selectbackground="#ffd700",
            selectforeground="black",
            height=4,
            bd=0,
            highlightthickness=0
        )
        self.server_list.pack(pady=10, padx=10, fill="both")

        self.connect_btn = tk.Button(
            conn_frame,
            text="🎮 Connect to Server",
            font=("Arial", 13, "bold"),
            bg="#ffd700",
            fg="black",
            activebackground="#ffed4e",
            command=self.connect_to_server,
            cursor="hand2",
            bd=0,
            padx=20,
            pady=8
        )
        self.connect_btn.pack(pady=5)

        # Game Area
        game_frame = tk.Frame(self.root, bg="#0d5c2d")
        game_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # Dealer Section
        dealer_section = tk.Frame(game_frame, bg="#1a4d2e", bd=2, relief="solid")
        dealer_section.pack(fill="both", expand=True, pady=5)

        tk.Label(
            dealer_section,
            text="🎩 DEALER",
            font=("Arial", 16, "bold"),
            bg="#1a4d2e",
            fg="#ffd700"
        ).pack(pady=5)

        self.dealer_cards_label = tk.Label(
            dealer_section,
            text="",
            font=("Courier", 24, "bold"),
            bg="#1a4d2e",
            fg="white",
            pady=10
        )
        self.dealer_cards_label.pack()

        self.dealer_sum_label = tk.Label(
            dealer_section,
            text="Sum: 0",
            font=("Arial", 14, "bold"),
            bg="#1a4d2e",
            fg="#90EE90"
        )
        self.dealer_sum_label.pack(pady=5)

        # Player Section
        player_section = tk.Frame(game_frame, bg="#2d5a3d", bd=2, relief="solid")
        player_section.pack(fill="both", expand=True, pady=5)

        tk.Label(
            player_section,
            text="👤 YOU",
            font=("Arial", 16, "bold"),
            bg="#2d5a3d",
            fg="#ffd700"
        ).pack(pady=5)

        self.player_cards_label = tk.Label(
            player_section,
            text="",
            font=("Courier", 24, "bold"),
            bg="#2d5a3d",
            fg="white",
            pady=10
        )
        self.player_cards_label.pack()

        self.player_sum_label = tk.Label(
            player_section,
            text="Sum: 0",
            font=("Arial", 14, "bold"),
            bg="#2d5a3d",
            fg="#90EE90"
        )
        self.player_sum_label.pack(pady=5)

        # Action Buttons
        action_frame = tk.Frame(self.root, bg="#0d5c2d")
        action_frame.pack(pady=10)

        self.hit_btn = tk.Button(
            action_frame,
            text="🃏 HIT",
            font=("Arial", 18, "bold"),
            bg="#28a745",
            fg="white",
            activebackground="#218838",
            width=12,
            command=self.hit,
            cursor="hand2",
            bd=0,
            pady=10,
            state="disabled"
        )
        self.hit_btn.pack(side="left", padx=10)

        self.stand_btn = tk.Button(
            action_frame,
            text="✋ STAND",
            font=("Arial", 18, "bold"),
            bg="#dc3545",
            fg="white",
            activebackground="#c82333",
            width=12,
            command=self.stand,
            cursor="hand2",
            bd=0,
            pady=10,
            state="disabled"
        )
        self.stand_btn.pack(side="left", padx=10)

        # Status Bar
        self.status = tk.Label(
            self.root,
            text="🔍 Looking for servers...",
            font=("Arial", 11),
            bg="#0a3d1f",
            fg="white",
            anchor="w",
            padx=10,
            pady=5
        )
        self.status.pack(side="bottom", fill="x")

    def update_stats(self):
        """Update statistics display"""
        self.stats_label.config(
            text=f"Wins: {self.wins} | Losses: {self.losses} | Ties: {self.ties} | Round: {self.current_round}/{self.num_rounds}"
        )

    def update_display(self):
        """Update card displays"""
        # Player cards
        player_display = " ".join([card_to_display(r, s) for r, s in self.player_cards])
        self.player_cards_label.config(text=player_display if player_display else "No cards")
        player_sum = calculate_hand(self.player_cards) if self.player_cards else 0
        self.player_sum_label.config(text=f"Sum: {player_sum}")

        # Dealer cards
        dealer_display = " ".join([card_to_display(r, s) for r, s in self.dealer_cards])
        self.dealer_cards_label.config(text=dealer_display if dealer_display else "??")
        dealer_sum = calculate_hand(self.dealer_cards) if self.dealer_cards else 0
        self.dealer_sum_label.config(text=f"Sum: {dealer_sum}")

    def start_udp_listener(self):
        """Listen for UDP broadcasts"""

        def listen():
            udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except AttributeError:
                udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            udp_socket.bind(("", UDP_PORT))

            while True:
                try:
                    data, addr = udp_socket.recvfrom(BUFFER_SIZE)
                    result = protocol.unpack_offer(data)

                    if result:
                        server_port, server_name = result
                        server_ip = addr[0]
                        self.add_server(server_name, server_ip, server_port)
                except Exception as e:
                    print(f"UDP Error: {e}")

        thread = threading.Thread(target=listen, daemon=True)
        thread.start()

    def add_server(self, name, ip, port):
        """Add server to list"""
        server_id = f"{ip}:{port}"
        if server_id not in self.servers:
            self.servers[server_id] = (name, ip, port)
            self.server_list.insert(tk.END, f"🎰 {name} ({ip}:{port})")
            self.status.config(text=f"✅ Found {len(self.servers)} server(s)")

    def connect_to_server(self):
        """Connect to selected server"""
        selection = self.server_list.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a server first!")
            return

        idx = selection[0]
        server_id = list(self.servers.keys())[idx]
        name, ip, port = self.servers[server_id]

        # Ask for rounds
        num_rounds = simpledialog.askinteger(
            "Number of Rounds",
            "How many rounds would you like to play?",
            minvalue=1,
            maxvalue=100,
            initialvalue=3
        )

        if not num_rounds:
            return

        self.num_rounds = num_rounds
        self.current_round = 0
        self.wins = 0
        self.losses = 0
        self.ties = 0
        self.update_stats()

        # Connect
        try:
            self.status.config(text=f"🔄 Connecting to {name}...")
            self.game_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.game_socket.connect((ip, port))

            # Send request
            request = protocol.pack_request(num_rounds, "GUI-Client")
            self.game_socket.sendall(request)

            self.connected = True
            self.connect_btn.config(state="disabled")
            self.status.config(text=f"✅ Connected to {name}! Starting game...")

            # Start game thread
            game_thread = threading.Thread(target=self.game_loop, daemon=True)
            game_thread.start()

        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to connect: {e}")
            self.status.config(text="❌ Connection failed")

    def recv_all(self, n):
        """Receive exactly n bytes"""
        data = b''
        while len(data) < n:
            try:
                packet = self.game_socket.recv(n - len(data))
                if not packet:
                    return None
                data += packet
            except:
                return None
        return data

    def game_loop(self):
        """Main game loop"""
        try:
            while self.current_round < self.num_rounds:
                self.play_round()
                time.sleep(2)

            # Game over
            self.root.after(0, self.show_game_over)

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Game Error", f"Error: {e}"))
            self.root.after(0, self.reset_game)

    def play_round(self):
        """Play one round"""
        self.current_round += 1
        self.player_cards = []
        self.dealer_cards = []
        self.my_turn = True
        self.cards_received = 0

        self.root.after(0, self.update_stats)
        self.root.after(0, self.update_display)
        self.root.after(0, lambda: self.status.config(text=f"🎲 Round {self.current_round} starting..."))

        while True:
            packet = self.recv_all(9)
            if not packet:
                raise Exception("Server disconnected")

            parsed = protocol.unpack_server_payload(packet)
            if not parsed:
                continue

            result, rank, suit = parsed

            # Game ended
            if result != 0:
                self.handle_round_end(result, rank, suit)
                break

            # Active game
            self.cards_received += 1
            self.handle_card(rank, suit)

    def handle_card(self, rank, suit):
        """Handle receiving a card"""
        if self.my_turn:
            if self.cards_received <= 2:
                self.player_cards.append((rank, suit))
            elif self.cards_received == 3:
                self.dealer_cards.append((rank, suit))
            else:
                self.player_cards.append((rank, suit))
        else:
            self.dealer_cards.append((rank, suit))

        self.root.after(0, self.update_display)

        # Enable buttons after initial deal
        if self.my_turn and self.cards_received >= 3:
            self.root.after(0, lambda: self.hit_btn.config(state="normal"))
            self.root.after(0, lambda: self.stand_btn.config(state="normal"))
            self.root.after(0, lambda: self.status.config(text="🤔 Your turn! Hit or Stand?"))

    def handle_round_end(self, result, rank, suit):
        """Handle round end"""
        # Add final card
        if result == 2 and self.my_turn:
            self.player_cards.append((rank, suit))
        else:
            self.dealer_cards.append((rank, suit))

        self.root.after(0, self.update_display)

        # Update stats
        if result == 3:
            self.wins += 1
            msg = "🎉 YOU WON!"
            color = "#28a745"
        elif result == 2:
            self.losses += 1
            msg = "😞 YOU LOST!"
            color = "#dc3545"
        else:
            self.ties += 1
            msg = "🤝 IT'S A TIE!"
            color = "#ffc107"

        self.root.after(0, self.update_stats)
        self.root.after(0, lambda: self.status.config(text=msg, bg=color))
        self.root.after(0, lambda: self.hit_btn.config(state="disabled"))
        self.root.after(0, lambda: self.stand_btn.config(state="disabled"))

        time.sleep(0.5)
        self.root.after(0, lambda: self.status.config(bg="#0a3d1f"))

    def hit(self):
        """Send Hit command"""
        if self.game_socket and self.my_turn:
            try:
                self.game_socket.sendall(protocol.pack_client_payload("Hittt"))
                self.hit_btn.config(state="disabled")
                self.stand_btn.config(state="disabled")
                self.status.config(text="🃏 Hit! Waiting for card...")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to send: {e}")

    def stand(self):
        """Send Stand command"""
        if self.game_socket and self.my_turn:
            try:
                self.game_socket.sendall(protocol.pack_client_payload("Stand"))
                self.my_turn = False
                self.hit_btn.config(state="disabled")
                self.stand_btn.config(state="disabled")
                self.status.config(text="✋ Standing. Dealer's turn...")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to send: {e}")

    def show_game_over(self):
        """Show game over screen"""
        win_rate = (self.wins / self.num_rounds * 100) if self.num_rounds > 0 else 0

        msg = f"Game Over!\n\n"
        msg += f"Rounds Played: {self.num_rounds}\n"
        msg += f"Wins: {self.wins}\n"
        msg += f"Losses: {self.losses}\n"
        msg += f"Ties: {self.ties}\n"
        msg += f"Win Rate: {win_rate:.1f}%\n\n"

        if win_rate >= 50:
            msg += "🏆 Great job!"
        else:
            msg += "🎰 The house always wins!"

        messagebox.showinfo("Game Over", msg)
        self.reset_game()

    def reset_game(self):
        """Reset game state"""
        if self.game_socket:
            self.game_socket.close()

        self.connected = False
        self.game_socket = None
        self.player_cards = []
        self.dealer_cards = []
        self.current_round = 0

        self.connect_btn.config(state="normal")
        self.hit_btn.config(state="disabled")
        self.stand_btn.config(state="disabled")
        self.update_display()
        self.update_stats()
        self.status.config(text="🔍 Looking for servers...", bg="#0a3d1f")

    def run(self):
        """Start the GUI"""
        self.root.mainloop()


if __name__ == "__main__":
    app = BlackjackGUI()
    app.run()