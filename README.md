# Multiplayer Blackjack – Client/Server over UDP and TCP

A networked Blackjack game written in Python for a Data Communications course. A server hosts games for several players at once, and clients find the server automatically on the local network.

Built by Dekel Winkler and [partner's name].

## How it works

1. **Discovery (UDP):** the server broadcasts an *offer* message every second on UDP port `13122`. A client listens on that port and learns the server's IP and TCP port.
2. **Game session (TCP):** the client connects over TCP, sends a *request* with its name and the number of rounds, and then plays: it sends `Hittt` or `Stand` decisions and receives cards and results.
3. **Concurrency:** each connected client is handled by a worker from a thread pool, so several players can play at the same time. Shared statistics are protected with a lock.
4. **Robustness:** the server uses timeouts and handles clients that disconnect in the middle of a game.

## Protocol

All messages are binary, packed with Python's `struct` in network byte order. Every message starts with a magic cookie (`0xabcddcba`) and a message type, and is validated on receipt.

| Message | Direction | Fields |
|---|---|---|
| Offer (`0x2`) | server → client (UDP) | cookie, type, server TCP port, server name (32 bytes) |
| Request (`0x3`) | client → server (TCP) | cookie, type, number of rounds, client name (32 bytes) |
| Payload (`0x4`) | client → server | cookie, type, decision (`Hittt` / `Stand`) |
| Payload (`0x4`) | server → client | cookie, type, round result, card rank, card suit |

## Files

| File | Description |
|---|---|
| `server.py` | UDP offer broadcasting and multi-threaded TCP game handling |
| `protocol.py` | Packing and unpacking of all binary messages |
| `game_logic.py` | Blackjack rules and deck management |
| `client_console.py` | Terminal client |
| `blackjack_client_gui.py` | Graphical client (Tkinter) |
| `bot_test.py`, `stress_test.py` | Automated clients for testing, including a stress test with 50 concurrent bots |
| `sniffer.py` | Small utility that prints raw UDP packets, used for debugging |

## Running

Start the server:
```bash
python server.py
```

In another terminal, start one or more clients:
```bash
python client_console.py
# or the graphical client (requires Pillow):
pip install pillow
python blackjack_client_gui.py
```

Run the stress test against a running server:
```bash
python stress_test.py
```
