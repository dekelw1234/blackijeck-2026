import random

class BlackjackGame:
    def __init__(self):
        # Create deck: Ranks 1-13, Suits 0-3
        self.deck = [(rank, suit) for rank in range(1, 14) for suit in range(4)]
        random.shuffle(self.deck)

    def draw_card(self):
        """
        Draws a card from the deck.
        If the deck is empty, creates and shuffles a new one.
        """
        if not self.deck:
            self.deck = [(rank, suit) for rank in range(1, 14) for suit in range(4)]
            random.shuffle(self.deck)
        return self.deck.pop()

    def calculate_hand(self, cards):
        """
        Calculates the sum of the hand according to Blackjack rules.
        Aces count as 11 unless the total exceeds 21, then they count as 1.
        """
        total = 0
        aces = 0

        for rank, suit in cards:
            if rank == 1:  # Ace
                aces += 1
                total += 11
            elif rank >= 10:  # Face cards (J, Q, K)
                total += 10
            else:
                total += rank

        # Handle Aces (convert from 11 to 1 if busted)
        while total > 21 and aces > 0:
            total -= 10
            aces -= 1

        return total

    def get_winner(self, player_cards, dealer_cards):
        """
        Determines the winner based on card sums.
        Returns:
        1 = Tie
        2 = Player Loss (Dealer Wins)
        3 = Player Win
        """
        player_sum = self.calculate_hand(player_cards)
        dealer_sum = self.calculate_hand(dealer_cards)

        if player_sum > 21:
            return 2  # Player busted
        if dealer_sum > 21:
            return 3  # Dealer busted
        if player_sum > dealer_sum:
            return 3
        if dealer_sum > player_sum:
            return 2
        return 1  # Tie