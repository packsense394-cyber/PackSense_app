#!/usr/bin/env python3

from neo4j import GraphDatabase
import json
import os
from typing import Dict, List, Tuple

class Neo4jCooccurrenceGraph:
    def __init__(self, uri="bolt://localhost:7687", user="neo4j", password="password"):
        """Initialize Neo4j connection"""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        
    def close(self):
        """Close the database connection"""
        self.driver.close()
        
    def clear_database(self):
        """Clear all nodes and relationships from the database"""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            
    def create_cooccurrence_graph(self, cooccurrence_data: Dict, reviews: List[Dict]):
        """Create co-occurrence graph in Neo4j"""
        with self.driver.session() as session:
            # Clear existing data
            session.run("MATCH (n) DETACH DELETE n")
            
            # Create nodes for each term
            for term in cooccurrence_data.keys():
                session.run(
                    "CREATE (t:Term {name: $name})",
                    name=term
                )
            
            # Create relationships for co-occurrences
            for term1, connections in cooccurrence_data.items():
                for term2, weight in connections.items():
                    if weight > 0:
                        session.run(
                            """
                            MATCH (t1:Term {name: $term1})
                            MATCH (t2:Term {name: $term2})
                            CREATE (t1)-[:COOCCURS_WITH {weight: $weight}]->(t2)
                            """,
                            term1=term1, term2=term2, weight=weight
                        )
            
            # Add review data as properties to terms
            for term in cooccurrence_data.keys():
                # Find reviews containing this term
                term_reviews = []
                for review in reviews:
                    if term.lower() in str(review.get('review_text', '')).lower():
                        term_reviews.append({
                            'title': review.get('review_title', ''),
                            'text': review.get('review_text', ''),
                            'reviewer': review.get('reviewer_name', ''),
                            'rating': review.get('rating', ''),
                            'sentiment': review.get('sentiment', '')
                        })
                
                # Update term with review data
                session.run(
                    """
                    MATCH (t:Term {name: $name})
                    SET t.reviews = $reviews
                    """,
                    name=term, reviews=json.dumps(term_reviews)
                )
    
    def get_term_details(self, term_name: str) -> Dict:
        """Get detailed information about a term including related reviews"""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Term {name: $name})
                OPTIONAL MATCH (t)-[:COOCCURS_WITH]->(related:Term)
                RETURN t.name as name, t.reviews as reviews, 
                       collect({name: related.name, weight: related.weight}) as connections
                """,
                name=term_name
            )
            
            record = result.single()
            if record:
                return {
                    'name': record['name'],
                    'reviews': json.loads(record['reviews']) if record['reviews'] else [],
                    'connections': record['connections']
                }
            return None
    
    def get_network_data(self) -> Dict:
        """Get all network data for visualization"""
        with self.driver.session() as session:
            # Get all nodes
            nodes_result = session.run("MATCH (t:Term) RETURN t.name as name")
            nodes = [{'id': record['name'], 'name': record['name']} for record in nodes_result]
            
            # Get all relationships
            relationships_result = session.run(
                """
                MATCH (t1:Term)-[r:COOCCURS_WITH]->(t2:Term)
                RETURN t1.name as source, t2.name as target, r.weight as weight
                """
            )
            relationships = [
                {
                    'source': record['source'],
                    'target': record['target'],
                    'weight': record['weight']
                }
                for record in relationships_result
            ]
            
            return {
                'nodes': nodes,
                'relationships': relationships
            }
    
    def get_related_terms(self, term_name: str, max_terms: int = 5) -> List[Dict]:
        """Get terms most related to a given term"""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Term {name: $name})-[r:COOCCURS_WITH]->(related:Term)
                RETURN related.name as name, r.weight as weight
                ORDER BY r.weight DESC
                LIMIT $limit
                """,
                name=term_name, limit=max_terms
            )
            
            return [
                {'name': record['name'], 'weight': record['weight']}
                for record in result
            ]

def create_neo4j_cooccurrence_graph(cooccurrence_data: Dict, reviews: List[Dict], 
                                   uri="bolt://localhost:7687", user="neo4j", password="password"):
    """Convenience function to create Neo4j co-occurrence graph"""
    try:
        graph = Neo4jCooccurrenceGraph(uri, user, password)
        graph.create_cooccurrence_graph(cooccurrence_data, reviews)
        return graph
    except Exception as e:
        print(f"Error connecting to Neo4j: {e}")
        print("Make sure Neo4j is running and accessible at the specified URI")
        return None

def get_neo4j_network_data(uri="bolt://localhost:7687", user="neo4j", password="password"):
    """Get network data from existing Neo4j database"""
    try:
        graph = Neo4jCooccurrenceGraph(uri, user, password)
        return graph.get_network_data()
    except Exception as e:
        print(f"Error connecting to Neo4j: {e}")
        return None
