from flask import Flask, render_template, request, jsonify
import chess
import random

app = Flask(__name__)

# Global board, move history, and pending promotion
board = chess.Board()
move_history = []  # Store board states
pending_promotion = None  # Store move waiting for promotion piece

def evaluate_board(board):
    """Evaluate the board position. Positive = good for White, negative = good for Black."""
    if board.is_checkmate():
        return -9999 if board.turn == chess.WHITE else 9999
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    piece_values = {
        chess.PAWN: 1,
        chess.KNIGHT: 3,
        chess.BISHOP: 3,
        chess.ROOK: 5,
        chess.QUEEN: 9,
        chess.KING: 0
    }

    score = 0
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece:
            value = piece_values[piece.piece_type]
            score += value if piece.color == chess.WHITE else -value

    return score

def calculate_score(board):
    """Calculate material score for display."""
    piece_values = {
        chess.PAWN: 1,
        chess.KNIGHT: 3,
        chess.BISHOP: 3,
        chess.ROOK: 5,
        chess.QUEEN: 9,
        chess.KING: 0
    }

    score = 0
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece:
            value = piece_values[piece.piece_type]
            score += value if piece.color == chess.WHITE else -value

    return score

def minimax(board, depth, maximizing_player):
    """Simple minimax algorithm to find the best move."""
    if depth == 0 or board.is_game_over():
        return evaluate_board(board), None

    legal_moves = list(board.legal_moves)
    if maximizing_player:
        max_eval = float('-inf')
        best_move = None
        for move in legal_moves:
            board.push(move)
            eval_score, _ = minimax(board, depth - 1, False)
            board.pop()
            if eval_score > max_eval:
                max_eval = eval_score
                best_move = move
        return max_eval, best_move
    else:
        min_eval = float('inf')
        best_move = None
        for move in legal_moves:
            board.push(move)
            eval_score, _ = minimax(board, depth - 1, True)
            board.pop()
            if eval_score < min_eval:
                min_eval = eval_score
                best_move = move
        return min_eval, best_move

def get_ai_move(board, depth=2):
    """Get the AI's move using minimax."""
    _, move = minimax(board, depth, False)
    if move is None:
        legal_moves = list(board.legal_moves)
        return random.choice(legal_moves) if legal_moves else None
    return move

@app.route('/')
def index():
    """Render the main chess game page."""
    score = calculate_score(board)
    return render_template('index.html', board=board.fen(), status="Your move (White).", score=score)

@app.route('/move', methods=['POST'])
def make_move():
    """Handle human move and return AI response."""
    global board, move_history, pending_promotion
    data = request.json
    move_uci = data.get('move')
    promotion_piece = data.get('promotion')  # Optional: q, b, n, r

    # Save current state for undo
    move_history.append(board.fen())

    # Handle promotion selection
    if pending_promotion and promotion_piece:
        try:
            promotion_map = {'q': chess.QUEEN, 'b': chess.BISHOP, 'n': chess.KNIGHT, 'r': chess.ROOK}
            if promotion_piece not in promotion_map:
                move_history.pop()
                return jsonify({'error': 'Invalid promotion piece! Choose q, b, n, or r.'})
            move = chess.Move.from_uci(pending_promotion + promotion_piece)
            if move in board.legal_moves:
                board.push(move)
                pending_promotion = None
            else:
                move_history.pop()
                return jsonify({'error': 'Illegal promotion move!'})
        except ValueError:
            move_history.pop()
            return jsonify({'error': 'Invalid move format!'})
    else:
        # Validate and process human move
        try:
            move = chess.Move.from_uci(move_uci)
            # Check if move requires promotion
            piece = board.piece_at(move.from_square)
            to_rank = chess.square_rank(move.to_square)
            if piece and piece.piece_type == chess.PAWN and to_rank == 7:  # White pawn to rank 8
                pending_promotion = move_uci
                return jsonify({'status': 'Choose promotion piece (q, b, n, r)', 'fen': board.fen(), 'score': calculate_score(board)})
            if move in board.legal_moves:
                board.push(move)
            else:
                move_history.pop()
                return jsonify({'error': 'Illegal move!'})
        except ValueError:
            move_history.pop()
            return jsonify({'error': 'Invalid move format!'})

    # Check game status
    status = ''
    is_checkmate = board.is_checkmate()
    if is_checkmate:
        status = f"Checkmate! {'Black' if board.turn == chess.WHITE else 'White'} wins!"
    elif board.is_stalemate():
        status = "Stalemate! Game is a draw."
    elif board.is_insufficient_material():
        status = "Draw due to insufficient material."
    elif board.is_check():
        status = "Check!"
    else:
        status = "Your move (White)."

    # AI move (Black)
    ai_move = None
    if not board.is_game_over() and board.turn == chess.BLACK:
        ai_move = get_ai_move(board, depth=2)
        if ai_move:
            # Check if AI move is a promotion
            piece = board.piece_at(ai_move.from_square)
            to_rank = chess.square_rank(ai_move.to_square)
            if piece and piece.piece_type == chess.PAWN and to_rank == 0:  # Black pawn to rank 1
                ai_move = chess.Move(ai_move.from_square, ai_move.to_square, promotion=chess.QUEEN)  # Default to queen
            board.push(ai_move)
            # Update status after AI move
            if board.is_checkmate():
                status = "Checkmate! Black wins!"
            elif board.is_stalemate():
                status = "Stalemate! Game is a draw."
            elif board.is_insufficient_material():
                status = "Draw due to insufficient material."
            elif board.is_check():
                status = "Check!"

    score = calculate_score(board)
    return jsonify({
        'fen': board.fen(),
        'status': status,
        'ai_move': ai_move.uci() if ai_move else None,
        'score': score,
        'checkmate': is_checkmate
    })

@app.route('/undo', methods=['POST'])
def undo():
    """Undo the last move (both human and AI)."""
    global board, move_history, pending_promotion
    if pending_promotion:
        pending_promotion = None
        move_history.pop()
        return jsonify({'fen': board.fen(), 'status': 'Your move (White).', 'score': calculate_score(board)})
    if move_history:
        board = chess.Board(move_history.pop())
    score = calculate_score(board)
    return jsonify({'fen': board.fen(), 'status': 'Your move (White).', 'score': score})

@app.route('/reset', methods=['POST'])
def reset():
    """Reset the game to the initial position."""
    global board, move_history, pending_promotion
    board = chess.Board()
    move_history = []
    pending_promotion = None
    score = calculate_score(board)
    return jsonify({'fen': board.fen(), 'status': 'Your move (White).', 'score': score})

if __name__ == '__main__':
    app.run(debug=True)