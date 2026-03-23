# Rule: Streamlit conventions

## Page structure

- `app.py` is the main page — all core dashboard logic lives here
- Additional pages go in `pages/` with a descriptive filename
- Every page file must call `st.set_page_config()` as its first Streamlit call
- Never split `app.py` into multiple files without careful consideration of
  `@st.cache_data` scope — cache is per-module

## Caching rules

Apply `@st.cache_data` to every data loader function. Exceptions:
- `load_overrides()` — intentionally NOT cached so admin edits apply immediately
- Any function that reads a file the user may edit during a session

If a cached function's output changes (e.g. new player file added), users must
clear cache manually via the Streamlit menu, or the app must be restarted.

## State management

- Use `st.session_state` sparingly — only for state that must persist across
  reruns and cannot be derived from the current inputs
- Sidebar controls drive all filtering — do not duplicate filter state

## HTML rendering

Custom HTML is rendered via `st.markdown(..., unsafe_allow_html=True)`.
All custom components (metric cards, profile card, peer banners, section
headers) use inline styles and CSS classes defined in the `<style>` block
at the top of `app.py`.

When adding new HTML components:
- Add CSS to the existing `<style>` block, not in a separate `st.markdown()` call
- Follow the existing naming convention: `.mc` (metric card), `.profile-card`, etc.
- Dark theme only — no light mode assumptions

## Error handling

- All file operations must handle missing files gracefully
- When a data file is missing, show a Streamlit warning, not a Python exception
- `st.stop()` is used after a fatal data load failure — this is intentional
- Never hide exceptions in data processing — surface them with `st.error()` + `st.exception()`

## Performance

- Heavy computations (percentile ranking across full peer groups) happen once
  per filter change thanks to `@st.cache_data`
- Do not loop over rows with `iterrows()` for large datasets — use vectorised pandas
- The match log filter (`search` text input) is the one place row-level filtering
  is acceptable as it operates on an already-small DataFrame
