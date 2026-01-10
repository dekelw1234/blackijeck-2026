Blackjack Client-Server Project
-------------------------------
Student Name: [Your Name Here]
Course: Data Communications

Description:
------------
This project implements a networked Blackjack game using Python.
It consists of a server that broadcasts offers via UDP and handles multiple
clients via TCP threads, and a client that connects and plays rounds of Blackjack.

Files:
------
1. server.py     - Multi-threaded server logic. Handles UDP broadcasts and TCP games.
2. client.py     - Client logic. Connects to server, handles user input and game display.
3. protocol.py   - Handles packing/unpacking of binary messages (structs).
4. game_logic.py - Contains the Blackjack rules and deck management.

How to Run:
-----------
1. Start the Server:
   Run the following command in a terminal:
   $ python server.py

   The server will bind to a random TCP port and start broadcasting UDP offers on port 13122.

2. Start the Client:
   Run the following command in a separate terminal (can run multiple instances):
   $ python client.py

   The client will listen for UDP offers, connect to the server, and ask for the number of rounds.

Protocol Format:
----------------
- Magic Cookie: 0xabcddcba (4 bytes)
- Message Types: Offer(0x2), Request(0x3), Payload(0x4)
- Fixed length structures used for all packets.

Special Features:
-----------------
- Solved TCP Packet Coalescing: Implemented delays and precise packet handling.
- Double-Bust Prevention: Fixed logic to ensure game state remains consistent on busts.
- Thread Safety: Used threading locks for global statistics.
- Robustness: Server handles unexpected disconnections and timeouts (60 seconds).