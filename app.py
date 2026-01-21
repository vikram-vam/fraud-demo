import streamlit as st
from streamlit_agraph import agraph, Node, Edge, Config
import pandas as pd
from neo4j_utils import init_driver, run_query, is_connected
from data_generator import generate_scenario_data

# ==============================================================================
# PAGE CONFIGURATION
# ==============================================================================
st.set_page_config(
    page_title="Graph vs. Relational: Auto Insurance Fraud",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .header-box {
        padding: 20px;
        border-radius: 10px;
        background: linear-gradient(90deg, #2c3e50 0%, #4ca1af 100%);
        color: white;
        margin-bottom: 20px;
    }
    .story-box {
        padding: 15px;
        border-left: 4px solid #3498db;
        background-color: #f0f7fb;
        border-radius: 4px;
        margin-bottom: 20px;
        color: #2c3e50;
    }
    .sql-box {
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 15px;
        background-color: #f8fafc;
        height: 100%;
    }
    .graph-box {
        border: 2px solid #4299e1;
        border-radius: 8px;
        padding: 15px;
        background-color: #ffffff;
        height: 100%;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# VISUALIZATION HELPERS
# ==============================================================================
def render_graph(data, height=500):
    """Renders the interactive graph."""
    nodes = []
    edges = []
    
    # Auto Insurance Color Palette
    type_colors = {
        'Person': '#3498db',       # Blue
        'Claim': '#9b59b6',        # Purple
        'Shop': '#e67e22',         # Orange
        'Doctor': '#2ecc71',       # Green
        'Policy': '#34495e',       # Dark Grey
        'Vehicle': '#95a5a6',      # Grey
        'Phone': '#e74c3c',        # Red
        'Address': '#f1c40f',      # Yellow
        'Attorney': '#8e44ad',     # Violet
    }

    for n in data['nodes']:
        color = type_colors.get(n['type'], '#718096')
        if n.get('is_fraud'): color = '#c0392b' # Dark Red for confirmed fraud
        if n.get('flagged'): color = '#d35400' # Burnt Orange for flagged entities
        
        # Build Rich Tooltip
        props = n.get('properties', {})
        tooltip_lines = [f"📌 {n['label']}"]
        tooltip_lines.append(f"Type: {n['type']}")
        
        # Display ROLE if available (New Data Structure)
        if 'role' in props: tooltip_lines.append(f"👤 Role: {props['role']}")
        
        # Add specific properties if they exist
        if 'amount' in props: tooltip_lines.append(f"💰 Amount: ${props['amount']:,}")
        if 'tenure' in props: tooltip_lines.append(f"⏳ Tenure: {props['tenure']}")
        if 'date' in props: tooltip_lines.append(f"📅 Date: {props['date']}")
        
        # Add ID at the bottom
        tooltip_lines.append(f"ID: {n.get('id')}")

        nodes.append(Node(
            id=n['id'],
            label=n['label'],
            size=30 if n['type'] in ['Claim', 'Policy'] else 25,
            shape='dot',
            color=color,
            title="\n".join(tooltip_lines)
        ))

    for e in data['edges']:
        edges.append(Edge(
            source=e['source'],
            target=e['target'],
            label="", # Hidden static label
            title=f"Relationship: {e['type']}", # Relationship shown on hover
            color='#bdc3c7'
        ))

    config = Config(
        width="100%",
        height=height,
        directed=True,
        physics=True,
        hierarchical=False,
    )
    
    with st.container(border=True):
        return agraph(nodes=nodes, edges=edges, config=config)

# ==============================================================================
# SCENARIO RENDERERS
# ==============================================================================

def render_scenario_1_discovery():
    """Network Discovery Scenario."""
    st.markdown("""
    <div class="header-box">
        <h2>1. Network Discovery: The "Recycled Passenger" Ring</h2>
        <p><strong>P&C Use Case:</strong> Detecting organized groups who stage accidents, recycling the same participants as passengers across multiple claims.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="story-box">
        <strong>📜 The Scenario:</strong><br>
        <strong>Accident #1 (Jan 2024):</strong> Driver A files a claim. Passengers B and C claim soft tissue injuries. Treated at <em>'Elite Rehab Center'</em>.<br>
        <strong>Accident #2 (Apr 2024):</strong> Driver D files a claim. <strong>Passenger B</strong> (from the first accident) is in the car again, along with new Passenger E. Also treated at <em>'Elite Rehab Center'</em>.
        <br><br>
        <strong>The Red Flag:</strong> It is statistically improbable for the same "Passenger B" to be in two injury-causing accidents with different drivers in 3 months, all using the same rehab center. Graph analysis exposes the <strong>"Recycled Passenger"</strong> pattern (Bowtie Topology) and links the Drivers via a shared burner phone.
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 🏛️ The Relational (SQL) View")
        st.info("SQL databases store claims as isolated rows. Finding 'Passenger B' across millions of rows requires expensive self-joins.")
        
        st.markdown("**Claims Table**")
        df_claims = pd.DataFrame([
            {"Claim": "CLM-101", "Date": "2024-01-10", "Driver": "Driver A", "Injured": "Pass B, Pass C"},
            {"Claim": "CLM-102", "Date": "2024-04-22", "Driver": "Driver D", "Injured": "Pass B, Pass E"},
        ])
        st.table(df_claims)
        
        st.markdown("**Provider Table**")
        df_prov = pd.DataFrame([
            {"Claim": "CLM-101", "Provider": "Elite Rehab Center"},
            {"Claim": "CLM-102", "Provider": "Elite Rehab Center"},
        ])
        st.table(df_prov)

        st.warning("⚠️ The connection is buried. Driver A and Driver D look unrelated. Passenger B is just a name text field in many systems.")

    with col2:
        st.markdown("### 🕸️ The Graph View")
        st.success("The 'Bowtie' pattern is unmistakable. Passenger B bridges the two accidents, and the Drivers are linked by a hidden phone.")
        
        if st.button("🔄 Generate Ring Data"):
            with st.spinner("Generating recycled passenger ring..."):
                generate_scenario_data(1)
                st.rerun()

        # Fetch Data - Captures the Recycled Passenger, Claims, Drivers, and Facilitators
        data = run_query("""
        MATCH path=(c:Claim)-[*1..3]-(related)
        WHERE c.id IN ['CLM-101', 'CLM-102']
        RETURN path LIMIT 100
        """)
        
        if data:
            render_graph(data, height=500)
            st.markdown("**Insight:** **Passenger B** is the nexus. **Elite Rehab** and **Lawyer Saul** facilitate both claims. **Driver A** and **Driver D** are colluding (Shared Phone).")
        else:
            st.warning("No data. Click 'Generate' above.")

def render_scenario_2_latent():
    """Latent Relationships Scenario."""
    st.markdown("""
    <div class="header-box">
        <h2>2. Latent Relationships: Witness Independence Verification</h2>
        <p><strong>P&C Use Case:</strong> Validating "Independent Witnesses" to rule out collusion or staged events.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="story-box">
        <strong>📜 The Scenario:</strong><br>
        <strong>Alice</strong> files a claim for a parking lot accident. A witness, <strong>Bob</strong>, provides a statement corroborating her version of events.
        To the adjuster, Bob appears to be an independent bystander.
        However, Graph analysis reveals a "Latent Link": Bob shares a mobile number or address history with <strong>Charlie</strong>, who is a known associate of Alice or a frequent claimant.
        This undisclosed relationship voids the witness's credibility and suggests a staged event.
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 🏛️ The Relational (SQL) View")
        st.write("Two claims appear independent. Different policies, different vehicles.")
        
        st.markdown("**Claim A (Alice)**")
        st.json({"ID": "CLM-A", "Policy": "POL-A", "Witness": "Bob"})
        
        st.markdown("**Claim B (Charlie)**")
        st.json({"ID": "CLM-B", "Policy": "POL-B", "Claimant": "Charlie"})
        
        st.error("🚨 There is no database key linking 'Witness Bob' to 'Claimant Charlie'. The fraud is hidden in the unstructured relationship.")

    with col2:
        st.markdown("### 🕸️ The Graph View")
        st.write("Graph traversal finds the **Shared Phone Number** linking the Witness of Claim A to the Claimant of Claim B.")
        
        if st.button("🔄 Generate Latent Data"):
             with st.spinner("Planting hidden link..."):
                generate_scenario_data(2)
                st.rerun()

        # Update Query to fetch broader context (Policies, Vehicles, Shops)
        data = run_query("""
        MATCH path = (root:Claim)-[*1..3]-(leaf)
        WHERE root.id IN ['CLM-A', 'CLM-B']
        RETURN path LIMIT 150
        """)

        if data:
            render_graph(data, height=500)
            st.success("✅ **Fraud Detected:** Witness Bob uses the same phone number as Charlie (Claimant B). This suggests collusion.")
        else:
            st.warning("No data. Click 'Generate' above.")

def render_scenario_3_false_positives():
    """False Positive Mitigation Scenario."""
    st.markdown("""
    <div class="header-box">
        <h2>3. False Positive Mitigation: Early Tenure Claims Analysis</h2>
        <p><strong>P&C Use Case:</strong> Distinguishing "Application Fraud" (buying policy to claim) from legitimate "Bad Luck" for new business.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="story-box">
        <strong>📜 The Scenario:</strong><br>
        Two major claims just hit the desk, both for <strong>$25,000</strong> in severe damages.
        <ul>
            <li><strong>Claim 999:</strong> Policyholder for 10 years (Loyal Customer). Accident is verified by police report.</li>
            <li><strong>Claim 888:</strong> Policy bound <strong>3 days ago</strong>. First payment. Vehicle towed to a non-network shop.</li>
        </ul>
        Legacy systems flag <strong>BOTH</strong> due to the high dollar amount. Graph analysis isolates the 10-year customer (Green/Safe) vs. the 3-day customer linked to a "Watchlist" shop (Red/Risk), allowing for Straight-Through-Processing (STP) of the legitimate claim.
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 🏛️ Rule-Based System (SQL)")
        st.markdown("Traditional SIU systems flag claims based on static business rules (e.g., Amount > $20k).")
        
        st.markdown("**SIU Alert Queue**")
        df_flags = pd.DataFrame([
            {"Claim": "CLM-999", "Amount": "$25,000", "Tenure": "120 Mo", "Alert": "HIGH SEVERITY"},
            {"Claim": "CLM-888", "Amount": "$25,000", "Tenure": "1 Mo", "Alert": "HIGH SEVERITY"}
        ])
        st.table(df_flags)
        st.error("🚨 Both claims are flagged. Investigators waste time reviewing the legitimate customer (CLM-999).")

    with col2:
        st.markdown("### 🕸️ The Graph View")
        st.write("Graph context immediately exonerates CLM-999 (Isolated, Long Tenure) and indicts CLM-888 (Connected to Fraud Ring).")
        
        if st.button("🔄 Generate Context Data"):
             with st.spinner("Generating context..."):
                generate_scenario_data(3)
                st.rerun()

        # Visualization
        c_a, c_b = st.tabs(["Claim CLM-999 (Legitimate)", "Claim CLM-888 (Risky)"])
        
        with c_a:
            data_legit = run_query("MATCH path=(c:Claim {id:'CLM-999'})-[*1..2]-(n) RETURN path")
            if data_legit:
                render_graph(data_legit, height=350)
                st.success("✅ **Recommendation: AUTO-APPROVE.** Long tenure policy, reputable repair shop, no connections to bad actors.")
            else:
                st.warning("No data generated.")
                
        with c_b:
            data_fraud = run_query("MATCH path=(c:Claim {id:'CLM-888'})-[*1..2]-(n) RETURN path")
            if data_fraud:
                render_graph(data_fraud, height=350)
                st.error("🚨 **Recommendation: INVESTIGATE.** New policy (1 mo), connected to 'Shady Body Shop' which is linked to past fraud.")
            else:
                st.warning("No data generated.")

# ==============================================================================
# MAIN APP LOGIC
# ==============================================================================

def main():
    if not is_connected():
        init_driver()
        
    st.sidebar.title("🔍 Investigation Scenarios")
    scenario = st.sidebar.radio(
        "Select a Demo Story:",
        ["1. Network Discovery", "2. Latent Relationships", "3. False Positive Mitigation"]
    )
    
    st.sidebar.markdown("---")
    st.sidebar.info("This demo generates synthetic Auto Insurance data (Policies, Claims, Vehicles) to demonstrate Graph DB advantages.")

    if "Network Discovery" in scenario:
        render_scenario_1_discovery()
    elif "Latent Relationships" in scenario:
        render_scenario_2_latent()
    elif "False Positive" in scenario:
        render_scenario_3_false_positives()

if __name__ == "__main__":
    main()