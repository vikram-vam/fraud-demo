from neo4j_utils import run_query_transaction
import random

def generate_scenario_data(scenario_id):
    """
    Generates Auto Insurance specific graph topologies.
    """
    # Clean database for clean demo slate
    run_query_transaction(["MATCH (n) DETACH DELETE n"])

    if scenario_id == 1:
        _create_discovery_ring()
    elif scenario_id == 2:
        _create_latent_link()
    elif scenario_id == 3:
        _create_false_positive_context()

def _create_discovery_ring():
    """
    Scenario 1: The 'Recycled Passenger' Ring.
    A sophisticated ring where 'passengers' cycle through staged accidents.
    Topology: Two accident clusters sharing a Passenger and a Service Nexus.
    """
    queries = [
        # --- The Facilitators (The Hubs) ---
        "CREATE (:Doctor {id:'DOC-X', label:'Elite Rehab Center', type:'Doctor', flagged:true})",
        "CREATE (:Attorney {id:'ATT-Y', label:'Lawyer Saul', type:'Attorney', flagged:true})",
        
        # --- Accident 1: The 'Setup' ---
        "CREATE (:Claim {id:'CLM-101', label:'Accident #1 ($45k)', type:'Claim', amount:45000, date:'2024-01-10'})",
        "CREATE (:Person {id:'Driver-A', label:'Driver A', role:'Organizer', type:'Person'})",
        
        # The Recycled Passenger (The key node)
        "CREATE (:Person {id:'Pass-B', label:'Passenger B', role:'Recycled Passenger', type:'Person', flagged:true})",
        "CREATE (:Person {id:'Pass-C', label:'Passenger C', role:'Passenger', type:'Person'})",
        
        "MATCH (d:Person {id:'Driver-A'}), (c:Claim {id:'CLM-101'}) CREATE (d)-[:FILED]->(c)",
        "MATCH (p:Person {id:'Pass-B'}), (c:Claim {id:'CLM-101'}) CREATE (p)-[:PASSENGER_IN]->(c)",
        "MATCH (p:Person {id:'Pass-C'}), (c:Claim {id:'CLM-101'}) CREATE (p)-[:PASSENGER_IN]->(c)",
        
        # Treatment & Legal for Acc 1
        "MATCH (c:Claim {id:'CLM-101'}), (d:Doctor {id:'DOC-X'}) CREATE (c)-[:TREATED_AT]->(d)",
        "MATCH (c:Claim {id:'CLM-101'}), (a:Attorney {id:'ATT-Y'}) CREATE (c)-[:REPRESENTED_BY]->(a)",

        # --- Accident 2: The 'Copycat' (3 months later) ---
        "CREATE (:Claim {id:'CLM-102', label:'Accident #2 ($38k)', type:'Claim', amount:38000, date:'2024-04-22'})",
        "CREATE (:Person {id:'Driver-D', label:'Driver D', role:'Organizer', type:'Person'})",
        "CREATE (:Person {id:'Pass-E', label:'Passenger E', role:'Passenger', type:'Person'})",
        
        "MATCH (d:Person {id:'Driver-D'}), (c:Claim {id:'CLM-102'}) CREATE (d)-[:FILED]->(c)",
        
        # RECYCLED PASSENGER B appears again in a different car!
        "MATCH (p:Person {id:'Pass-B'}), (c:Claim {id:'CLM-102'}) CREATE (p)-[:PASSENGER_IN]->(c)",
        "MATCH (p:Person {id:'Pass-E'}), (c:Claim {id:'CLM-102'}) CREATE (p)-[:PASSENGER_IN]->(c)",
        
        # Same Facilitators
        "MATCH (c:Claim {id:'CLM-102'}), (d:Doctor {id:'DOC-X'}) CREATE (c)-[:TREATED_AT]->(d)",
        "MATCH (c:Claim {id:'CLM-102'}), (a:Attorney {id:'ATT-Y'}) CREATE (c)-[:REPRESENTED_BY]->(a)",
        
        # --- The Hidden Link (The Organizers share a burner phone) ---
        "CREATE (:Phone {id:'PH-RING', label:'Burner Phone', type:'Phone', flagged:true})",
        "MATCH (d1:Person {id:'Driver-A'}), (ph:Phone {id:'PH-RING'}) CREATE (d1)-[:HAS_PHONE]->(ph)",
        "MATCH (d2:Person {id:'Driver-D'}), (ph:Phone {id:'PH-RING'}) CREATE (d2)-[:HAS_PHONE]->(ph)"
    ]
    run_query_transaction(queries)

def _create_latent_link():
    """
    Scenario 2: Latent Relationships (The 'Compromised Witness').
    Creates a fuller graph context with vehicles, repair shops, and doctors.
    """
    queries = [
        # --- Cluster A: Alice's Accident ---
        "CREATE (:Person {id:'Alice', label:'Alice', role:'Claimant', type:'Person'})",
        "CREATE (:Policy {id:'POL-A', label:'Policy #A-991', type:'Policy', tenure:'3 Years'})",
        "CREATE (:Vehicle {id:'VEH-A', label:'2020 Ford Fusion', type:'Vehicle'})",
        "CREATE (:Claim {id:'CLM-A', label:'Claim #A-22', type:'Claim', amount:4500, date:'2024-03-10'})",
        
        "MATCH (p:Person {id:'Alice'}), (pol:Policy {id:'POL-A'}) CREATE (p)-[:HOLDER]->(pol)",
        "MATCH (pol:Policy {id:'POL-A'}), (v:Vehicle {id:'VEH-A'}) CREATE (pol)-[:COVERS]->(v)",
        "MATCH (p:Person {id:'Alice'}), (c:Claim {id:'CLM-A'}) CREATE (p)-[:FILED]->(c)",
        "MATCH (c:Claim {id:'CLM-A'}), (v:Vehicle {id:'VEH-A'}) CREATE (c)-[:INVOLVES]->(v)",
        
        "CREATE (:Shop {id:'SHOP-A', label:'Downtown Auto', type:'Shop'})",
        "MATCH (c:Claim {id:'CLM-A'}), (s:Shop {id:'SHOP-A'}) CREATE (c)-[:REPAIRED_AT]->(s)",

        "CREATE (:Person {id:'Wit-Bob', label:'Bob', role:'Witness', type:'Person'})",
        "MATCH (w:Person {id:'Wit-Bob'}), (c:Claim {id:'CLM-A'}) CREATE (w)-[:WITNESSED]->(c)",
        
        # --- Cluster B: Charlie's Accident ---
        "CREATE (:Person {id:'Charlie', label:'Charlie', role:'Claimant', type:'Person'})",
        "CREATE (:Policy {id:'POL-B', label:'Policy #B-772', type:'Policy', tenure:'6 Months'})",
        "CREATE (:Vehicle {id:'VEH-B', label:'2016 Chevy Malibu', type:'Vehicle'})",
        "CREATE (:Claim {id:'CLM-B', label:'Claim #B-44', type:'Claim', amount:5200, date:'2024-04-05'})",
        
        "MATCH (p:Person {id:'Charlie'}), (pol:Policy {id:'POL-B'}) CREATE (p)-[:HOLDER]->(pol)",
        "MATCH (pol:Policy {id:'POL-B'}), (v:Vehicle {id:'VEH-B'}) CREATE (pol)-[:COVERS]->(v)",
        "MATCH (p:Person {id:'Charlie'}), (c:Claim {id:'CLM-B'}) CREATE (p)-[:FILED]->(c)",
        "MATCH (c:Claim {id:'CLM-B'}), (v:Vehicle {id:'VEH-B'}) CREATE (c)-[:INVOLVES]->(v)",
        
        "CREATE (:Doctor {id:'DOC-B', label:'Metro Health', type:'Doctor'})",
        "MATCH (c:Claim {id:'CLM-B'}), (d:Doctor {id:'DOC-B'}) CREATE (c)-[:TREATED_AT]->(d)",
        
        # --- The Latent Link ---
        "CREATE (:Phone {id:'PH-555', label:'555-0199', type:'Phone', flagged:true})",
        "MATCH (w:Person {id:'Wit-Bob'}), (ph:Phone {id:'PH-555'}) CREATE (w)-[:HAS_PHONE]->(ph)",
        "MATCH (p:Person {id:'Charlie'}), (ph:Phone {id:'PH-555'}) CREATE (p)-[:HAS_PHONE]->(ph)"
    ]
    run_query_transaction(queries)

def _create_false_positive_context():
    """
    Scenario 3: False Positive Mitigation (Contextual Analysis).
    """
    queries = [
        # 1. The False Positive (Legitimate High Value Claim)
        "CREATE (:Person {id:'L-User', label:'Loyal Customer', role:'Insured', type:'Person'})",
        "CREATE (:Policy {id:'POL-L', label:'Policy (10 Yrs)', type:'Policy', tenure:'120 Months'})",
        "CREATE (:Claim {id:'CLM-999', label:'Major Accident ($25k)', type:'Claim', amount:25000})",
        
        "MATCH (p:Person {id:'L-User'}), (pol:Policy {id:'POL-L'}) CREATE (p)-[:HOLDER]->(pol)",
        "MATCH (p:Person {id:'L-User'}), (c:Claim {id:'CLM-999'}) CREATE (p)-[:FILED]->(c)",
        
        "CREATE (:Shop {id:'S-Dealer', label:'Official Dealer', type:'Shop'})",
        "MATCH (c:Claim {id:'CLM-999'}), (s:Shop {id:'S-Dealer'}) CREATE (c)-[:REPAIRED_AT]->(s)",

        # 2. The True Positive (Fraud High Value Claim)
        "CREATE (:Person {id:'F-User', label:'New Customer', role:'Insured', type:'Person'})",
        "CREATE (:Policy {id:'POL-F', label:'Policy (1 Mo)', type:'Policy', tenure:'1 Month'})",
        "CREATE (:Claim {id:'CLM-888', label:'Major Accident ($25k)', type:'Claim', amount:25000})",
        
        "MATCH (p:Person {id:'F-User'}), (pol:Policy {id:'POL-F'}) CREATE (p)-[:HOLDER]->(pol)",
        "MATCH (p:Person {id:'F-User'}), (c:Claim {id:'CLM-888'}) CREATE (p)-[:FILED]->(c)",
        
        "CREATE (:Shop {id:'S-Shady', label:'Shady Body Shop', type:'Shop', flagged:true})",
        "MATCH (c:Claim {id:'CLM-888'}), (s:Shop {id:'S-Shady'}) CREATE (c)-[:REPAIRED_AT]->(s)",
        
        "CREATE (:Claim {id:'CLM-OLD', label:'Past Fraud Claim', type:'Claim', is_fraud:true})",
        "MATCH (c:Claim {id:'CLM-OLD'}), (s:Shop {id:'S-Shady'}) CREATE (c)-[:REPAIRED_AT]->(s)"
    ]
    run_query_transaction(queries)