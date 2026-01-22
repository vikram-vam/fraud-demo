# From Tables to Triangles: A Relational Veteran’s Guide to Graph Databases

**Target Audience:** Experienced SQL/RDBMS Developers
**Goal:** Translate relational concepts into Graph (Neo4j) architecture for Fraud Detection.
**Estimated Read Time:** 10 Minutes

---

## 1. The Source Data: Our Starting Point

Before we talk about graphs, let's look at the data exactly as it sits in your RDBMS today. We have three tables: two "Entity" tables and one "Event/Join" table.

**Table A: USERS (The Left Entity)**
| user_id (PK) | name | risk_score |
| :--- | :--- | :--- |
| 101 | Alice | 0.1 |
| 102 | Bob | 0.8 |

**Table B: DEVICES (The Right Entity)**
| device_id (PK) | type | ip_address |
| :--- | :--- | :--- |
| D1 | Mobile | 192.168.1.5 |
| D2 | Desktop | 10.0.0.1 |

**Table C: LOGINS (The Join / Transaction)**
In SQL, this is just another table containing Foreign Keys.
| login_id (PK) | user_id_fk | device_id_fk | timestamp |
| :--- | :--- | :--- | :--- |
| 1 | 101 | D1 | 09:00 AM |
| 2 | 102 | D2 | 09:05 AM |
| 3 | 102 | D1 | 09:30 AM |

---

## 2. The Migration Strategy: Online vs. Offline

How do we physically move this data? There are two distinct roads, depending on your volume.

### Method A: The "Online" Transactional Load (The Surgical Approach)
* **Best for:** Day-to-day updates, real-time streams, or smaller datasets (<10M records).
* **Mechanism:** You run Cypher `CREATE` or `MERGE` statements while the database is running.
* **Pros:** The database remains online; you can query data immediately.
* **Cons:** Slower for massive loads because every row pays the "ACID transaction tax" (locking, logging).

**The Process with Python (Pseudo-Code):** In this method, the logic lives inside the Python script and the Database query.

**Step 0: Create Constraints (Run in Neo4j Browser)** If you don't create an Index/Constraint first, every `MERGE` command has to scan the entire table to check if a user exists. Your script will start fast and get exponentially slower.
```cypher
// cypher code
// 1. Initialize User Constraints
CREATE CONSTRAINT FOR (u:User) REQUIRE u.user_id IS UNIQUE;

// 2. Initialize Device Constraints
CREATE CONSTRAINT FOR (d:Device) REQUIRE d.device_id IS UNIQUE;
```

```python
# python_loader.py
from neo4j import GraphDatabase
import pandas as pd

# 1. Read ALL your SQL Exports
users_df = pd.read_csv("users.csv")     # Contains: 101, Alice, 0.1
devices_df = pd.read_csv("devices.csv") # Contains: D1, Mobile, 192.168...
logins_df = pd.read_csv("logins.csv")   # Contains: 1, 101, D1, 09:00

# 2. Connect to the Graph
driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))

# --- Define Transaction Functions ---
def create_user(tx, uid, name, risk):
    tx.run("MERGE (u:User {id: $id}) SET u.name = $name, u.risk_score = $risk", 
           id=uid, name=name, risk=risk)

def create_device(tx, did, dtype, ip):
    # This was missing! We need to set the specific device properties.
    tx.run("MERGE (d:Device {id: $id}) SET d.type = $dtype, d.ip_address = $ip", 
           id=did, dtype=dtype, ip=ip)

def create_login_link(tx, uid, did, time):
    # Now we just match the existing nodes and draw the line
    query = """
    MATCH (u:User {id: $uid})
    MATCH (d:Device {id: $did})
    MERGE (u)-[:LOGGED_IN_WITH {timestamp: $time}]->(d)
    """
    tx.run(query, uid=uid, did=did, time=time)

# 3. Execution Phase (Nouns First, then Verbs)
with driver.session() as session:
    
    # Step A: Load Users
    print("Loading Users...")
    for _, row in users_df.iterrows():
        session.write_transaction(create_user, row['user_id'], row['name'], row['risk_score'])

    # Step B: Load Devices (The Missing Step!)
    print("Loading Devices...")
    for _, row in devices_df.iterrows():
        session.write_transaction(create_device, row['device_id'], row['type'], row['ip_address'])

    # Step C: Load Relationships
    print("Linking Data...")
    for _, row in logins_df.iterrows():
        session.write_transaction(create_login_link, row['user_id_fk'], row['device_id_fk'], row['timestamp'])

print("Graph Load Complete.")
```

### Method B: The "Offline" Bulk Load (The Industrial Approach)
* **Best for:** The initial migration of historical data (100M+ records). 
* **Mechanism:** We shut down the database engine. We use a command-line tool (`neo4j-admin import`) that reads CSVs and writes directly to the disk files (the "Store Files").
* **The Trick:** We format the headers specifically: `:START_ID`, `:END_ID`, and `:TYPE`.
* **Pros:** Blazing fast (millions of records per second). It bypasses the transaction engine entirely.
* **Cons:** The DB must be offline; requires strict CSV formatting. Zero logic allowed. If the CSV says "User 101 connects to Device 999" and Device 999 doesn't exist, the import might fail or create a ghost node. Ensure clean data before this step.

**Step 1: Data Prep (Python Script)**
We must transform your SQL tables into "Header-Formatted" CSVs.
* **Special Headers (`:ID`, `:START_ID`):** Tell the tool how to build the structure.
* **Regular Headers (`name`, `risk_score`):** Are automatically loaded as properties.
```python
# python_formatter.py
import pandas as pd

users = pd.read_csv("users.csv")
devices = pd.read_csv("devices.csv")
logins = pd.read_csv("logins.csv")

# 1. Rename Columns for Users
# We change the ID column to the special syntax.
# Crucial: 'name' and 'risk_score' are left alone, so they become properties automatically.
users_headers = users.rename(columns={'user_id': 'user_id:ID(User)'})

# 2. Rename Columns for Devices
# 'type' and 'ip_address' are left alone, so they become properties.
devices_headers = devices.rename(columns={'device_id': 'device_id:ID(Device)'})

# 3. Rename Columns for Logins (Relationships)
# We map the foreign keys to Start/End points.
# 'timestamp' is left alone, so it becomes a property of the relationship.
logins_headers = logins.rename(columns={
    'user_id_fk': ':START_ID(User)',
    'device_id_fk': ':END_ID(Device)',
    'timestamp': 'timestamp' 
})

# 4. Export to "Import-Ready" CSVs
users_headers.to_csv("users_header.csv", index=False)
devices_headers.to_csv("devices_header.csv", index=False)
logins_headers.to_csv("logins_header.csv", index=False)
```
**Step 2: The Command Line (No Code Logic)** We turn off the database and run the import command. It reads the files and builds the graph structure on disk.
```bash
# Terminal Command (Database is OFFLINE)
bin/neo4j-admin database import full \
    --nodes=import/users_header.csv \
    --nodes=import/devices_header.csv \
    --relationships=import/logins_header.csv \
    --overwrite-destination
```
* **What happens inside?** The tool reads `101` from the Start column, finds the memory pointer for Alice, reads `D1` from the End column, finds the memory pointer for the iPhone, and writes the connection directly to the disk.

**Step 3: The "Post-Load" Cleanup (Crucial)** Since the tool ran blindly, you might have loaded duplicates (e.g., two "Alice" nodes).
* **Start the Database.**
* **Try to Create Constraint**
    ```cypher
    // cypher code
    CREATE CONSTRAINT FOR (u:User) REQUIRE u.user_id IS UNIQUE;
    ```
* **If this fails:** It means you have duplicates. Run this "De-Dupe" script to clean the data, then try creating the constraint again.
    ```cypher
    // cypher code
    // Finds duplicates and deletes the extras
    MATCH (u:User)
    WITH u.user_id AS id, collect(u) AS nodes
    WHERE size(nodes) > 1
    FOREACH (n IN tail(nodes) | DETACH DELETE n)
    ```

---

## 3. The Core Concept: Deconstruction, Not Translation

If you have spent years designing normalized schemas (3NF), your brain is wired to think in **containers** (Tables) and **references** (Foreign Keys). To understand a Graph Database, you don't need to learn a new language; you just need to shift where you place the complexity.

In SQL, complexity lives in the **Query** (the Joins).
In Graph, complexity lives in the **Data Structure** (the Relationships).

### The Rosetta Stone

| Relational Concept (SQL) | Graph Concept (Neo4j) | The Shift in Thinking |
| :--- | :--- | :--- |
| **Table** | **Label** | Instead of a `Customers` table, we have nodes tagged `:Customer`. |
| **Row** | **Node** | A single record is an object. |
| **Foreign Key** | **Relationship** | **Crucial:** In SQL, a link is a *value* (ID). In Graph, a link is a physical *object*. |
| **Join Table** | **Relationship** | Many-to-Many tables (e.g., `User_Devices`) disappear; they become direct lines. |

---

## 4. Populating the Graph: The "Zipper" Strategy

How do we move data from rows and columns into a web of nodes? We don't just "copy tables." We deconstruct them into **Nouns** and **Verbs**.

### Phase A: Load the Nouns (Entities)
We ignore connections. We simply turn rows into Nodes.
* *SQL:* `SELECT * FROM Users`
* *Graph:* `CREATE (:User)`

### Phase B: Load the Verbs (Relationships)
This is the biggest shift. We take your **Join Tables** (Table C above) and turn them into connections.

**The Workflow:**
1.  Read the Join Table row: `[User_ID: 101, Device_ID: 'D1', Time: '09:00']`
2.  **Look up** Node 101 (The User).
3.  **Look up** Node D1 (The Device).
4.  **Draw the line** connecting them.

**Code Example (Cypher):**
```cypher
// cypher code
// We iterate through your "Logins" CSV file
LOAD CSV WITH HEADERS FROM 'file:///logins.csv' AS row

// 1. Find the Start Point
MATCH (u:User {id: row.user_id})

// 2. Find the End Point
MATCH (d:Device {id: row.device_id})

// 3. Create the Connection (The "Verb")
MERGE (u)-[r:LOGGED_IN_WITH]->(d)
SET r.timestamp = row.timestamp
```

---

## 5. Querying: From "Joining" to "Walking"

In SQL, finding "A connected to B connected to C" requires multiple expensive joins. In a Graph, we just describe the pattern.

### The Fraud Scenario: "The Triangle"
**Goal:** Find two distinct users who logged into the same device.

**The SQL Mental Model:**
> `SELECT ... FROM Logins L1 JOIN Logins L2 ON L1.DeviceID = L2.DeviceID ...`

**The Graph Mental Model:**
> "Find a User, follow the path to a Device, then follow the path backward to another User."

**The Cypher Query:**
```cypher
// cypher code
MATCH (u1:User)-[:LOGGED_IN_WITH]->(sharedDevice:Device)<-[:LOGGED_IN_WITH]-(u2:User)
WHERE u1.id < u2.id  // Prevent "Alice matches Alice"
RETURN u1.name, u2.name, sharedDevice.id
```

**Visual Output:** Instead of a grid, the database returns a shape: `(Alice) --> (D1) <-- (Bob)`

---

## 6. Algorithms: The Superpowers

This is where Graph leaves SQL in the dust. Instead of writing 100 lines of recursive SQL to find complex patterns, we call optimized algorithms.

### A. Weakly Connected Components (WCC)
* **The Question:** "Find all fraud rings. I don't care how deep they are (A->B->C->D...)."
* **The Algorithm:** It "colors" the graph. If Alice touches a device that Bob touches, they get the same color.
* **The Result:** We get a `fraudRingId` for every user. We can instantly group millions of users into isolated clusters.

### B. PageRank
* **The Question:** "Inside this fraud ring of 50 people, who is the Ringleader?"
* **The Algorithm:** It measures influence. A device used by 20 people is "heavier" than a device used by 1. A user connected to a "heavy" device becomes "heavy" themselves.
* **The Result:** We can sort nodes by `influence_score`. The top node is your root cause.

### C. Node Similarity (The "Copycat" Finder)

* **The Question** "What if the fraudsters are smart? What if they **never** share a device or a credit card?"
    They might still use the **same behavior patterns**.

    * User A: Buys `Diapers`, `Beer`, and `Peanuts` at `Store X`.
    * User B: Buys `Diapers`, `Beer`, and `Peanuts` at `Store X`.

    They have no direct link (no shared ID). But they are structurally identical.

* **The Algorithm (Jaccard Similarity):** It calculates the overlap of neighbors.

    **The Formula:**
    $$J(A,B) = \frac{|Neighbors(A) \cap Neighbors(B)|}{|Neighbors(A) \cup Neighbors(B)|}$$

    * If A and B have 100% overlap in transaction locations, Score = 1.0.
    * If they have 0% overlap, Score = 0.0.

* **The Application:** We run this algorithm to create **"SIMILAR_TO"** relationships between users who have never met. This exposes "Sybil Attacks" (one person pretending to be many) based purely on behavior.

---

## 8. Summary:

| Task | Relational (SQL) | Graph (Neo4j) |
| :--- | :--- | :--- |
| **Model** | Tables & Foreign Keys | Nodes & Relationships |
| **Join Data** | `JOIN ON table.id = table.id` | `(a)-[:REL]->(b)` |
| **Find Loops** | Recursive CTE (Complex/Slow) | Pattern Match (Native/Fast) |
| **Find Clusters** | Extremely difficult | **WCC Algorithm** |
| **Find Importance** | `COUNT(*)` | **PageRank** |
| **Find Copycats** | Complex Self-Joins | **Node Similarity** |