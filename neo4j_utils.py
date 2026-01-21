import streamlit as st
from neo4j import GraphDatabase

def init_driver():
    """Initialize Neo4j driver from secrets."""
    if 'neo4j_driver' not in st.session_state:
        try:
            secrets = st.secrets["neo4j"]
            driver = GraphDatabase.driver(
                secrets["uri"], 
                auth=(secrets["username"], secrets["password"])
            )
            driver.verify_connectivity()
            st.session_state.neo4j_driver = driver
        except Exception as e:
            st.error(f"Failed to connect to Neo4j: {e}")

def is_connected():
    return 'neo4j_driver' in st.session_state and st.session_state.neo4j_driver is not None

def run_query(query, params=None):
    """Run a query and return formatted for visualization."""
    if not is_connected(): return None
    
    with st.session_state.neo4j_driver.session() as session:
        result = session.run(query, params or {})
        
        # Parse into Agraph format
        nodes = {}
        edges = []
        
        for record in result:
            path = record['path']
            # Neo4j Path objects contain nodes and relationships
            for n in path.nodes:
                # Capture all properties for the rich tooltip
                props = dict(n)
                
                nodes[n.element_id] = {
                    'id': n.element_id,
                    'label': n.get('label', n.get('id', 'Node')),
                    'type': list(n.labels)[0] if n.labels else 'Unknown',
                    'is_fraud': n.get('is_fraud', False),
                    'flagged': n.get('flagged', False),
                    'properties': props  # Pass all properties to UI
                }
            
            for r in path.relationships:
                edges.append({
                    'source': r.start_node.element_id,
                    'target': r.end_node.element_id,
                    'type': r.type
                })
                
        return {'nodes': list(nodes.values()), 'edges': edges}

def run_query_transaction(queries):
    """Run a list of write queries."""
    if not is_connected(): return
    
    with st.session_state.neo4j_driver.session() as session:
        for q in queries:
            session.run(q)