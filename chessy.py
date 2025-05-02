from flask import Flask, render_template, request, jsonify, session
import chess
import random
import os
import uuid

app = Flask(__name__)
app.secret_key = os.urandom(24)
user_games = {}
def start_new_game():
    return {
        'board': chess.Board(),
        'move_history': [],
        'pending_promotion': None
    }

def get_user_game():
    user_id = session.get('user_id')
    if not user_id:
        user_id = str(uuid.uuid4())
        session['user_id'] = user_id
    if user_id not in user_games:
        user_games[user_id] = start_new_game()
    return user_games[user_id]
# Global board, move history, and pending promotion
board = chess.Board()
move_history = []  # Store board states
pending_promotion = None  # Store move waiting for promotion

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

            # Center control bonus (d4, d5, e4, e5)
            if square in [chess.D4, chess.D5, chess.E4, chess.E5]:
                if piece.piece_type in [chess.PAWN, chess.KNIGHT, chess.BISHOP]:
                    score += 0.3 if piece.color == chess.WHITE else -0.3

    # Mobility bonus: Reward pieces with more legal moves
    legal_moves = len(list(board.legal_moves))
    score += legal_moves * 0.1 if board.turn == chess.WHITE else -legal_moves * 0.1

    # King safety: Penalize exposed kings
    if board.king(chess.WHITE):
        white_king_sq = board.king(chess.WHITE)
        white_king_attacks = len(board.attacks(white_king_sq))
        score -= white_king_attacks * 0.2  # Penalty for attacks near king
    if board.king(chess.BLACK):
        black_king_sq = board.king(chess.BLACK)
        black_king_attacks = len(board.attacks(black_king_sq))
        score += black_king_attacks * 0.2

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

def sort_moves(board, moves):
    """Sort moves for alpha-beta pruning efficiency."""
    def move_score(move):
        score = 0
        # Prioritize captures
        if board.is_capture(move):
            score += 100
        # Prioritize checks
        board.push(move)
        if board.is_check():
            score += 50
        board.pop()
        # Prioritize promotions
        if move.promotion:
            score += 200
        return score

    return sorted(moves, key=move_score, reverse=True)

def minimax(board, depth, alpha, beta, maximizing_player):
    """Minimax with alpha-beta pruning."""
    if depth == 0 or board.is_game_over():
        return evaluate_board(board), None

    legal_moves = sort_moves(board, list(board.legal_moves))
    if maximizing_player:
        max_eval = float('-inf')
        best_move = None
        for move in legal_moves:
            board.push(move)
            eval_score, _ = minimax(board, depth - 1, alpha, beta, False)
            board.pop()
            if eval_score > max_eval:
                max_eval = eval_score
                best_move = move
            alpha = max(alpha, eval_score)
            if beta <= alpha:
                break  # Prune
        return max_eval, best_move
    else:
        min_eval = float('inf')
        best_move = None
        for move in legal_moves:
            board.push(move)
            eval_score, _ = minimax(board, depth - 1, alpha, beta, True)
            board.pop()
            if eval_score < min_eval:
                min_eval = eval_score
                best_move = move
            beta = min(beta, eval_score)
            if beta <= alpha:
                break  # Prune
        return min_eval, best_move

def get_ai_move(board, depth=3):
    """Get the AI's move using minimax with alpha-beta pruning."""
    _, move = minimax(board, depth, float('-inf'), float('inf'), False)
    if move is None:
        legal_moves = list(board.legal_moves)
        return random.choice(legal_moves) if legal_moves else None
    return move

@app.route('/')
def index():
    game = get_user_game()
    board = game['board']
    score = calculate_score(board)
    return render_template('index.html', board=board.fen(), status="Your move (White).", score=score)

@app.route('/move', methods=['POST'])
def make_move():
    game = get_user_game()
    board = game['board']
    move_history = game['move_history']
    pending_promotion = game['pending_promotion']

    data = request.json
    move_uci = data.get('move')
    promotion_piece = data.get('promotion')
    difficulty = int(data.get('difficulty', 3))

    move_history.append(board.fen())

    if pending_promotion and promotion_piece:
        try:
            promotion_map = {'q': chess.QUEEN, 'b': chess.BISHOP, 'n': chess.KNIGHT, 'r': chess.ROOK}
            if promotion_piece not in promotion_map:
                move_history.pop()
                return jsonify({'error': 'Invalid promotion piece!'})
            move = chess.Move.from_uci(pending_promotion + promotion_piece)
            if move in board.legal_moves:
                board.push(move)
                game['pending_promotion'] = None
            else:
                move_history.pop()
                return jsonify({'error': 'Illegal promotion move!'})
        except ValueError:
            move_history.pop()
            return jsonify({'error': 'Invalid move format!'})
    else:
        try:
            move = chess.Move.from_uci(move_uci)
            piece = board.piece_at(move.from_square)
            if not piece or piece.color != chess.WHITE:
                move_history.pop()
                return jsonify({'error': 'You can only move white pieces!'})
            to_rank = chess.square_rank(move.to_square)
            if piece.piece_type == chess.PAWN and to_rank == 7:
                game['pending_promotion'] = move_uci
                return jsonify({'status': 'Choose promotion piece (q, b, n, r)', 'fen': board.fen(), 'score': calculate_score(board)})
            if move in board.legal_moves:
                board.push(move)
            else:
                move_history.pop()
                return jsonify({'error': 'Illegal move!'})
        except ValueError:
            move_history.pop()
            return jsonify({'error': 'Invalid move format!'})

    status = "Your move (White)."
    if board.is_checkmate():
        status = f"Checkmate! {'Black wins! well tried champ' if board.turn == chess.WHITE else 'White wins! GG you are OG'} NOW ENTER THE FEEDBACK 🔫🔫 "
    elif board.is_stalemate():
        status = "Stalemate! Game is a draw."
    elif board.is_insufficient_material():
        status = "Draw due to insufficient material."
    elif board.is_check():
        status = "Check!"

    ai_move = None
    if not board.is_game_over() and board.turn == chess.BLACK:
        ai_move = get_ai_move(board, depth=difficulty)
        if ai_move:
            piece = board.piece_at(ai_move.from_square)
            to_rank = chess.square_rank(ai_move.to_square)
            if piece and piece.piece_type == chess.PAWN and to_rank == 0:
                ai_move = chess.Move(ai_move.from_square, ai_move.to_square, promotion=chess.QUEEN)
            board.push(ai_move)
            if board.is_checkmate():
                status = "Checkmate! Black wins!"
            elif board.is_stalemate():
                status = "Stalemate! Game is a draw."
            elif board.is_insufficient_material():
                status = "Draw due to insufficient material."
            elif board.is_check():
                status = "Check!"

    return jsonify({
        'fen': board.fen(),
        'status': status,
        'ai_move': ai_move.uci() if ai_move else None,
        'score': calculate_score(board),
        'checkmate': board.is_checkmate()
    })

@app.route('/undo', methods=['POST'])
def undo():
    game = get_user_game()
    board = game['board']
    move_history = game['move_history']
    pending_promotion = game['pending_promotion']

    if pending_promotion:
        game['pending_promotion'] = None
        move_history.pop()
    elif move_history:
        board.set_fen(move_history.pop())

    return jsonify({'fen': board.fen(), 'status': 'Your move (White).', 'score': calculate_score(board)})

@app.route('/reset', methods=['POST'])
def reset():
    user_id = session.get('user_id')
    if user_id:
        user_games[user_id] = start_new_game()
    game = user_games[user_id]
    board = game['board']
    return jsonify({'fen': board.fen(), 'status': 'Your move (White).', 'score': calculate_score(board)})

@app.route('/feedback', methods=['POST'])
def feedback():
    data = request.json
    feedback = data.get('feedback')
    if not feedback or len(feedback) > 250:
        return jsonify({'error': 'Feedback must be non-empty and at most 250 characters.'}), 400

    try:
        with open('feedback.txt', 'a') as f:
            f.write(f"{feedback}\n")
        return jsonify({'message': 'Feedback submitted successfully!'})
    except Exception:
        return jsonify({'error': 'Error saving feedback.'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0',port="5000",debug=True)
