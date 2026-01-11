import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import socket
import threading
import time
import protocol
from PIL import Image, ImageTk

# --- Constants ---
UDP_PORT = 13122
BUFFER_SIZE = 1024


# --- Card Display Helper ---
def card_to_display(rank, suit):
    """Converts card to readable string with emoji suits"""
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
        self.root.geometry("1024x768")

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

        # Store window references for repositioning
        self.windows = {}

        # Load background image
        try:
            self.bg_image_original = Image.open("blackjacktable.png")
            self.bg_photo = None
        except Exception as e:
            print(f"Error loading background: {e}")
            self.bg_image_original = None

        self.create_ui()
        self.start_udp_listener()

        # Bind resize event
        self.root.bind('<Configure>', self.on_resize)

    def on_resize(self, event):
        """Handle window resize - update background and reposition all elements"""
        if event.widget == self.root:
            width = event.width
            height = event.height

            # Resize background image
            if self.bg_image_original:
                resized = self.bg_image_original.resize((width, height), Image.LANCZOS)
                self.bg_photo = ImageTk.PhotoImage(resized)
                self.canvas.delete("bg")
                self.canvas.create_image(0, 0, image=self.bg_photo, anchor="nw", tags="bg")
                self.canvas.tag_lower("bg")

            # Update canvas size
            self.canvas.config(width=width, height=height)

            # Reposition all elements based on percentages
            self.reposition_elements(width, height)

    def reposition_elements(self, width, height):
        """Reposition all UI elements based on window size"""
        # Title (center top - 50%, 4%)
        self.canvas.coords(self.windows['title'], width * 0.5, height * 0.04)

        # Stats (top right - 85%, 4%)
        self.canvas.coords(self.windows['stats'], width * 0.85, height * 0.04)

        # Connection panel (top left - 15%, 10%)
        self.canvas.coords(self.windows['connection'], width * 0.15, height * 0.10)

        # Dealer cards (center, 35% from top)
        self.canvas.coords(self.windows['dealer'], width * 0.5, height * 0.35)

        # Player cards (center, 75% from top)
        self.canvas.coords(self.windows['player'], width * 0.5, height * 0.75)

        # Action buttons (center, 90% from top)
        self.canvas.coords(self.windows['actions'], width * 0.5, height * 0.90)

        # Status bar (center bottom, 97% from top)
        self.canvas.coords(self.windows['status'], width * 0.5, height * 0.97)

    def create_ui(self):
        """Build the interface with custom background"""

        # Main Canvas with background
        self.canvas = tk.Canvas(
            self.root,
            width=1024,
            height=768,
            highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)

        # Set initial background
        if self.bg_image_original:
            resized = self.bg_image_original.resize((1024, 768), Image.LANCZOS)
            self.bg_photo = ImageTk.PhotoImage(resized)
            self.canvas.create_image(0, 0, image=self.bg_photo, anchor="nw", tags="bg")
        else:
            self.canvas.configure(bg="#0d5c2d")

        # Title overlay (50%, 4%)
        title_frame = tk.Frame(self.canvas, bg="#1a1a1a", bd=2, relief="solid")
        self.windows['title'] = self.canvas.create_window(
            512, 30,
            window=title_frame,
            tags="overlay"
        )

        title = tk.Label(
            title_frame,
            text="♠️ BLACKJACK ♥️",
            font=("Arial", 28, "bold"),
            bg="#1a1a1a",
            fg="#ffd700",
            padx=30,
            pady=5
        )
        title.pack()

        # Stats Bar (85%, 4%)
        stats_frame = tk.Frame(self.canvas, bg="#1a1a1a", bd=2, relief="solid")
        self.windows['stats'] = self.canvas.create_window(
            870, 30,
            window=stats_frame,
            tags="overlay"
        )

        self.stats_label = tk.Label(
            stats_frame,
            text="W:0 L:0 T:0\nRound: 0/0",
            font=("Arial", 10, "bold"),
            bg="#1a1a1a",
            fg="white",
            padx=10,
            pady=5,
            justify="center"
        )
        self.stats_label.pack()

        # Server connection panel (15%, 10%)
        conn_frame = tk.Frame(self.canvas, bg="#1a1a1a", bd=2, relief="solid")
        self.windows['connection'] = self.canvas.create_window(
            150, 80,
            window=conn_frame,
            tags="overlay"
        )

        tk.Label(
            conn_frame,
            text="📡 Servers",
            font=("Arial", 11, "bold"),
            bg="#1a1a1a",
            fg="#ffd700"
        ).pack(pady=2)

        self.server_list = tk.Listbox(
            conn_frame,
            font=("Courier", 9),
            bg="#2d2d2d",
            fg="white",
            selectbackground="#ffd700",
            selectforeground="black",
            height=3,
            width=30,
            bd=0
        )
        self.server_list.pack(pady=3, padx=5)

        self.connect_btn = tk.Button(
            conn_frame,
            text="🎮 Connect",
            font=("Arial", 10, "bold"),
            bg="#ffd700",
            fg="black",
            command=self.connect_to_server,
            cursor="hand2",
            bd=0,
            padx=15,
            pady=3
        )
        self.connect_btn.pack(pady=5)

        # Dealer Cards Area (50%, 35%)
        dealer_card_frame = tk.Frame(self.canvas, bg="", bd=0)
        self.windows['dealer'] = self.canvas.create_window(
            512, 270,
            window=dealer_card_frame,
            tags="overlay"
        )

        self.dealer_cards_label = tk.Label(
            dealer_card_frame,
            text="",
            font=("Courier", 32, "bold"),
            bg="#0d5c2d",
            fg="white",
            bd=2,
            relief="solid",
            padx=20,
            pady=5
        )
        self.dealer_cards_label.pack()

        self.dealer_sum_label = tk.Label(
            dealer_card_frame,
            text="",
            font=("Arial", 14, "bold"),
            bg="#1a1a1a",
            fg="#90EE90",
            padx=10,
            pady=2
        )
        self.dealer_sum_label.pack(pady=3)

        # Player Cards Area (50%, 75%)
        player_card_frame = tk.Frame(self.canvas, bg="", bd=0)
        self.windows['player'] = self.canvas.create_window(
            512, 576,
            window=player_card_frame,
            tags="overlay"
        )

        self.player_cards_label = tk.Label(
            player_card_frame,
            text="",
            font=("Courier", 32, "bold"),
            bg="#0d5c2d",
            fg="white",
            bd=2,
            relief="solid",
            padx=20,
            pady=5
        )
        self.player_cards_label.pack()

        self.player_sum_label = tk.Label(
            player_card_frame,
            text="",
            font=("Arial", 14, "bold"),
            bg="#1a1a1a",
            fg="#90EE90",
            padx=10,
            pady=2
        )
        self.player_sum_label.pack(pady=3)

        # Action Buttons (50%, 90%)
        action_frame = tk.Frame(self.canvas, bg="")
        self.windows['actions'] = self.canvas.create_window(
            512, 691,
            window=action_frame,
            tags="overlay"
        )

        self.hit_btn = tk.Button(
            action_frame,
            text="🃏 HIT",
            font=("Arial", 16, "bold"),
            bg="#28a745",
            fg="white",
            width=10,
            command=self.hit,
            cursor="hand2",
            bd=0,
            pady=8,
            state="disabled"
        )
        self.hit_btn.pack(side="left", padx=15)

        self.stand_btn = tk.Button(
            action_frame,
            text="✋ STAND",
            font=("Arial", 16, "bold"),
            bg="#dc3545",
            fg="white",
            width=10,
            command=self.stand,
            cursor="hand2",
            bd=0,
            pady=8,
            state="disabled"
        )
        self.stand_btn.pack(side="left", padx=15)

        # Status Bar (50%, 97%)
        status_frame = tk.Frame(self.canvas, bg="#1a1a1a")
        self.windows['status'] = self.canvas.create_window(
            512, 745,
            window=status_frame,
            tags="overlay"
        )

        self.status = tk.Label(
            status_frame,
            text="🔍 Looking for servers...",
            font=("Arial", 11),
            bg="#1a1a1a",
            fg="white",
            padx=200,
            pady=5
        )
        self.status.pack()

    def update_stats(self):
        """Update statistics display"""
        self.stats_label.config(
            text=f"W:{self.wins} L:{self.losses} T:{self.ties}\nRound: {self.current_round}/{self.num_rounds}"
        )

    def update_display(self):
        """Update card displays"""
        # Player cards
        if self.player_cards:
            player_display = " ".join([card_to_display(r, s) for r, s in self.player_cards])
            self.player_cards_label.config(text=player_display)
            player_sum = calculate_hand(self.player_cards)
            self.player_sum_label.config(text=f"Sum: {player_sum}")
        else:
            self.player_cards_label.config(text="")
            self.player_sum_label.config(text="")

        # Dealer cards
        if self.dealer_cards:
            dealer_display = " ".join([card_to_display(r, s) for r, s in self.dealer_cards])
            self.dealer_cards_label.config(text=dealer_display)
            dealer_sum = calculate_hand(self.dealer_cards)
            self.dealer_sum_label.config(text=f"Sum: {dealer_sum}")
        else:
            self.dealer_cards_label.config(text="??")
            self.dealer_sum_label.config(text="")

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
            self.server_list.insert(tk.END, f"🎰 {name[:15]}")
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
            self.status.config(text=f"✅ Connected! Starting game...")

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
        self.root.after(0, lambda: self.status.config(bg="#1a1a1a"))

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
        """Show game over screen with animated GIF"""
        win_rate = (self.wins / self.num_rounds * 100) if self.num_rounds > 0 else 0

        # Create custom window
        game_over_window = tk.Toplevel(self.root)
        game_over_window.title("Game Over")
        game_over_window.geometry("500x600")
        game_over_window.configure(bg="#1a1a1a")
        game_over_window.resizable(False, False)

        # Center the window
        game_over_window.transient(self.root)
        game_over_window.grab_set()

        # Title
        title = tk.Label(
            game_over_window,
            text="🎰 GAME OVER 🎰",
            font=("Arial", 24, "bold"),
            bg="#1a1a1a",
            fg="#ffd700"
        )
        title.pack(pady=20)

        # GIF Animation
        gif_label = tk.Label(game_over_window, bg="#1a1a1a")
        gif_label.pack(pady=10)

        # Load appropriate GIF
        if win_rate >= 50:
            gif_path = "win.gif"
        else:
            gif_path = "lose.gif"

        # Load and animate GIF
        try:
            gif_image = Image.open(gif_path)
            frames = []

            # Extract all frames from GIF
            try:
                while True:
                    frame = gif_image.copy()
                    frame = frame.resize((300, 300), Image.LANCZOS)
                    frames.append(ImageTk.PhotoImage(frame))
                    gif_image.seek(len(frames))  # Move to next frame
            except EOFError:
                pass  # All frames extracted

            # Animate function
            def animate(frame_idx=0):
                if game_over_window.winfo_exists():
                    gif_label.config(image=frames[frame_idx])
                    frame_idx = (frame_idx + 1) % len(frames)
                    game_over_window.after(50, animate, frame_idx)  # 50ms = ~20fps

            animate()

        except Exception as e:
            print(f"Error loading GIF: {e}")
            # Fallback emoji if GIF fails
            emoji = "🏆" if win_rate >= 50 else "💔"
            gif_label.config(
                text=emoji,
                font=("Arial", 100),
                bg="#1a1a1a"
            )

        # Stats Panel
        stats_frame = tk.Frame(game_over_window, bg="#2d2d2d", bd=2, relief="solid")
        stats_frame.pack(pady=20, padx=40, fill="both")

        # Result message
        if win_rate >= 50:
            result_msg = "🎉 WINNER! 🎉"
            result_color = "#28a745"
        else:
            result_msg = "😔 Better luck next time!"
            result_color = "#dc3545"

        result_label = tk.Label(
            stats_frame,
            text=result_msg,
            font=("Arial", 18, "bold"),
            bg="#2d2d2d",
            fg=result_color,
            pady=10
        )
        result_label.pack()

        # Separator
        tk.Frame(stats_frame, bg="#ffd700", height=2).pack(fill="x", padx=20, pady=5)

        # Statistics
        stats_text = f"""
    Rounds Played: {self.num_rounds}

    Wins: {self.wins}
    Losses: {self.losses}
    Ties: {self.ties}

    Win Rate: {win_rate:.1f}%
    """

        stats_label = tk.Label(
            stats_frame,
            text=stats_text,
            font=("Arial", 14),
            bg="#2d2d2d",
            fg="white",
            justify="center"
        )
        stats_label.pack(pady=10)

        # Close button
        close_btn = tk.Button(
            game_over_window,
            text="✖ Close",
            font=("Arial", 14, "bold"),
            bg="#dc3545",
            fg="white",
            activebackground="#c82333",
            command=lambda: [game_over_window.destroy(), self.reset_game()],
            cursor="hand2",
            bd=0,
            padx=30,
            pady=10
        )
        close_btn.pack(pady=20)

        # Wait for window to close
        game_over_window.wait_window()

    # def show_game_over(self):
    #     """Show game over screen"""
    #     win_rate = (self.wins / self.num_rounds * 100) if self.num_rounds > 0 else 0
    #
    #     msg = f"Game Over!\n\n"
    #     msg += f"Rounds Played: {self.num_rounds}\n"
    #     msg += f"Wins: {self.wins}\n"
    #     msg += f"Losses: {self.losses}\n"
    #     msg += f"Ties: {self.ties}\n"
    #     msg += f"Win Rate: {win_rate:.1f}%\n\n"
    #
    #     if win_rate >= 50:
    #         msg += "🏆 Great job!"
    #     else:
    #         msg += "🎰 The house always wins!"
    #
    #     messagebox.showinfo("Game Over", msg)
    #     self.reset_game()
    #
    # def reset_game(self):
    #     """Reset game state"""
    #     if self.game_socket:
    #         self.game_socket.close()
    #
    #     self.connected = False
    #     self.game_socket = None
    #     self.player_cards = []
    #     self.dealer_cards = []
    #     self.current_round = 0
    #
    #     self.connect_btn.config(state="normal")
    #     self.hit_btn.config(state="disabled")
    #     self.stand_btn.config(state="disabled")
    #     self.update_display()
    #     self.update_stats()
    #     self.status.config(text="🔍 Looking for servers...", bg="#1a1a1a")

    def run(self):
        """Start the GUI"""
        self.root.mainloop()


if __name__ == "__main__":
    app = BlackjackGUI()
    app.run()