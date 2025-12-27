# Coding Conventions

## Fully Qualified Function Calling Policy

All project-specific functions MUST use fully qualified calling to maintain context and readability.

### Internal Usage (within project)

When calling functions from within the same project, import the module and use qualified calls:

```python
# tahoo project
from . import db
conn = db.store.connect(database)
prices = db.queries.get_prices(conn, tickers, start, end)
db.fetch.refresh_history(conn, settings, updates_path, tickers)
```

```python
# fid project
from . import db
from . import report

conn = db.store.connect(db_path)
data = db.queries.balance_data(conn, ticker, 'usd')
result = report.balance.calculate_running_balance(data)
```

### External Usage (cross-project)

When calling functions from external projects, include the project root for maximum clarity:

```python
# Using tahoo from another project
import tahoo
conn = tahoo.db.store.connect(db_path)
prices = tahoo.db.queries.get_prices(conn, ticker, start_date, end_date)
```

```python
# Using fid from another project
import fid
conn = fid.db.store.connect(db_path)
data = fid.db.queries.balance_data(conn, ticker, 'usd')
result = fid.report.balance.calculate_running_balance(data)
```

### Rationale

1. **Context is always visible**: `tahoo.db.queries.get_prices` immediately shows:
   - Which library (`tahoo`)
   - Which module (`db`)
   - Which submodule (`queries`)
   - What operation (`get_prices`)

2. **Shorter, verb-based function names**: The namespace provides context, so functions can use simple verbs:
   - `db.queries.get_prices` (not `query_prices_from_database`)
   - `db.store.connect` (not `connect_to_database`)
   - `db.fetch.refresh_history` (not `fetch_yahoo_history`)

3. **Unambiguous at call site**: No confusion about where functions come from

4. **No naming collisions**: Different modules can have similar function names

### Anti-patterns (DO NOT USE)

```python
# ❌ BAD: Direct function import loses context
from tahoo.db.queries import get_prices
prices = get_prices(conn, ticker)  # Where does this come from?

# ❌ BAD: Partial qualification loses project context
from tahoo import db
# ... in external script
prices = db.queries.get_prices(conn, ticker)  # Which project's db?

# ✅ GOOD: Full qualification
import tahoo
prices = tahoo.db.queries.get_prices(conn, ticker)
```

## Module Organization

Projects should organize code into logical modules:

```
project/
├── db/
│   ├── store.py      # Connection management: connect(), init_schema()
│   ├── queries.py    # Read operations: get_*(), calculate_*()
│   └── fetch.py      # External data: refresh_*(), update_*()
├── report/
│   └── module.py     # Reporting: show_*(), format_*()
└── cli/
    └── commands.py   # CLI commands
```

Function names within modules should:
- Start with verbs (get, calculate, show, refresh, connect)
- Be concise (context comes from qualified path)
- Describe the action clearly

## Database Access Pattern

External scripts should NEVER access databases directly. Always use the project's query interface:

```python
# ❌ BAD: Direct SQL access
import sqlite3
conn = sqlite3.connect(db_path)
df = pd.read_sql_query("SELECT * FROM table", conn)

# ✅ GOOD: Use project's query interface
import tahoo
conn = tahoo.db.store.connect(db_path)
df = tahoo.db.queries.get_prices(conn, ticker, start, end)
```

This ensures:
- Schema changes are isolated to query modules
- Business logic stays in one place
- External scripts don't break when database structure changes
