# Theatre Before The Theatre

Premium Flask + HTML/CSS/JS redesign of the existing Movie Booking Service.

## Safety / compatibility

- Existing MySQL database name remains `movie_booking_db`.
- No database schema migration is included.
- No startup CREATE DATABASE, ALTER TABLE, seat reset, or seed operation is executed.
- Browser JavaScript never connects directly to MySQL.
- Database and SMTP credentials are server-side environment variables.
- Existing booking, seat-hold, OTP, authentication and admin SQL behavior has been retained where it existed in the supplied application.

## Run

1. Start the existing MySQL server and make sure `movie_booking_db` already exists.
2. Copy `.env.example` to `.env` and set the server environment variables. Do not commit credentials.
3. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

4. Start:

```bash
python main.py
```

5. Open `http://127.0.0.1:5000`.

## Notes

The original Tkinter implementation is preserved as `legacy_tkinter_main.py` for rollback/reference. It is not imported by the web application.

The redesign adds theme persistence, cinematic transitions, 3D movie-card tilt, magnetic buttons, hover lighting, seat depth, cinema/focus presentation classes, responsive layouts, and reduced-motion support. These effects do not write to the database.
