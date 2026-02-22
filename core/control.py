# core/control.py

def panic_mode(st, exchange, db, telegram):

    st.paused = True
    db.save_state(st.__dict__)

    positions = exchange.get_open_positions()

    closed = 0

    for p in positions:
        try:
            exchange.close_position(p["symbol"])
            closed += 1
        except:
            pass

    telegram.send(
        f"🚨 <b>PANIC MODE ACTIVADO</b>\n\n"
        f"Bot pausado\n"
        f"Posiciones cerradas: {closed}"
    )

def close_all_positions(exchange):
    positions = exchange.get_open_positions()
    closed = 0
    for p in positions:
        exchange.close_position(p["symbol"])
        closed += 1
    return closed

def pause_bot(st, db):
    st.paused = True
    db.save_state(st.__dict__)

def resume_bot(st, db):
    st.paused = False
    db.save_state(st.__dict__)