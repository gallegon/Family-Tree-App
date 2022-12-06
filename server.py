from flask import Flask, render_template, request, redirect, url_for
import networkx as nx
from networkx.drawing.nx_agraph import write_dot, graphviz_layout
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure

import base64
from collections import defaultdict
import sqlite3

from os.path import exists

app = Flask(__name__)

matplotlib.use('Agg')  # workaround for GUI bug

DB_PATH = "./db/family_tree.db"

family_tree = nx.DiGraph()  # Initialize the graph object (Direct Graph)


# general functions

# Converts the directed graph to "parent-pair form".  Children are no longer
# direct descendants of parents.  There is an intermediate node called a 
# "parent-pair" which acts as a direct ancestor to a child and a direct child to a parent.
def convert_to_ppf(graph):
    ppf_graph = nx.DiGraph()

    # Copy nodes from passed graph into new representation
    for node in graph.nodes:
        person_name = graph.nodes[node]['name']
        ppf_graph.add_node(node, name=person_name)
        

    parent_pairs = set()

    # Maps a child to a list of it's parents
    ch_par_map = defaultdict(list)

    # Maps a parent to children
    par_child_map = defaultdict(list)
    # Maps a parent_pair to it's list of children
    pp_ch_map = defaultdict(list)

    for parent, child in graph.edges:
        ch_par_map[child].append(parent)
        par_child_map[parent].append(child)
    
    for child, parents in ch_par_map.items():
        num_parents = len(parents)
        if num_parents == 0:
            for ch in par_child_map[child]:
                ppf_graph.add_edge(child, ch)
            continue
        elif num_parents == 1:
            parent_id = parents[0]
            parent_pairs.add((0, parent_id))
            ppf_graph.add_edge(parent_id, child)
        else:
            parent_0 = parents[0]
            parent_1 = parents[1]
            pair = (parent_0, parent_1) if parent_0 > parent_1 else (parent_1, parent_0)
            parent_pairs.add(pair)
            pp_ch_map[pair].append(child)
            ppf_graph.add_node(pair)
            ppf_graph.add_edge(parent_0, pair)
            ppf_graph.add_edge(parent_1, pair)

    for parent_pair, children in pp_ch_map.items():
        p0, p1 = parent_pair
        # If only one parent is known
        if p0 == 0:
            for child in children:
                ppf_graph.add_edge(p1, child)
        else:
            for child in children:
                ppf_graph.add_edge(parent_pair, child)

    write_dot(ppf_graph,'test.dot')

    pos = graphviz_layout(ppf_graph, prog='dot')
    labels = nx.get_node_attributes(ppf_graph, 'name')
    plt.figure(3,figsize=(16,6))
    plt.clf()
    nx.draw(ppf_graph, pos, node_size=2000, labels=labels)

    # Save the figure
    plt.savefig('./static/ppf.png')
    #draw_pyvis_graph(ppf_graph, "ppf.html")

#routes
@app.route('/')
def Index():
    db_exists = exists(DB_PATH)

    # Open the database if one exists, otherwise create a database
    conn = sqlite3.connect(DB_PATH)

    # Create People and Parents_Children tables if this is a new database.
    if not db_exists:
        conn.execute("""CREATE TABLE People (
            id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            name varchar(255) DEFAULT NULL,
            bio mediumtext DEFAULT NULL);""")

        conn.execute("""CREATE TABLE Parents_Children (
            parent_id int(11) DEFAULT NULL,
            child_id int(11) DEFAULT NULL);""")
    
        conn.execute("INSERT INTO People (name, bio) VALUES ('Noel', 'Not christmas noel')")
    
        conn.commit()
    """
    The following code snippet initializes the NetworkX graph.  First nodes are created based on
    who is in the People table (specifically their unique IDs), then edges are assigned between
    nodes based on data in the Parents_Children table.
    """


    # Temporary tree that is reinstantiated every time the index is got.  
    # This is eventually copied to the global family_tree
    tree = nx.DiGraph()

    # Get IDs and names to use as nodes
    conn = sqlite3.connect(DB_PATH)
    node_list = conn.execute("SELECT id, name FROM People")

    # create nodes
    for id, person_name in node_list:
        print(f"{id} {person_name}")
        if tree.has_node(id):
            continue
        else:
            tree.add_node(id, name=person_name)
    
    #print(tree.number_of_nodes())
    #cursor.close()

    # create edges from edge list in database (Parents_Children table)
    edge_list = conn.execute("SELECT * FROM Parents_Children")

    parents_by_id = defaultdict(list)
    children_by_id = defaultdict(list)

    edge_list_details = []
    for parent_id, child_id in edge_list:
        if tree.has_edge(parent_id, child_id):
            continue
        else:
            tree.add_edge(parent_id, child_id)
        
        # get the name of the parent by querying the ID in people
        cursor = conn.execute(f'SELECT name FROM People WHERE id={parent_id}')
        name = cursor.fetchall()
        parent_name = name[0][0]

        # get the name of the child by querying the ID in people
        cursor = conn.execute(f'SELECT name FROM People WHERE id={child_id}')
        name = cursor.fetchall()
        child_name = name[0][0]

        # map each id to it's parents and children so we can access a node's children by name
        parents_by_id[child_id].append((parent_id, parent_name))
        children_by_id[parent_id].append((child_id, child_name))

        # Pack relative information about an edge into a tuple to be unpacked later
        edge_info = (parent_id, child_id, parent_name, child_name)
        edge_list_details.append(edge_info)


    #print(tree.number_of_edges())

    data = conn.execute("SELECT * FROM People")

    family_tree = tree

    plt.clf()

    write_dot(family_tree,'test.dot')

    pos = graphviz_layout(family_tree, prog='dot')
    labels = nx.get_node_attributes(family_tree, 'name')
    plt.figure(3,figsize=(16,6))
    nx.draw(family_tree, pos, node_size=2000, labels=labels)

    # Save the figure
    plt.savefig('./static/foo.png')

    convert_to_ppf(family_tree)
    # Open the new figure and convert to a base64 encoded image so that it can
    # be directly rendered to the flask template.
    with open('./static/ppf.png', 'rb') as tree_image:
        img_b64 = "data:image/png;base64,"
        img_b64 += base64.b64encode(tree_image.read()).decode('utf8')
    
    return render_template('index.html', title='Untitled app', people = data, 
                            family_tree_img = "./../static/foo.png", image=img_b64, 
                            edges=edge_list_details, parents=parents_by_id, children=children_by_id)

# add a person to the SQL database via a simple web form (for now)
@app.route('/add_person', methods=['POST'])
def add_person():
    if request.method == 'POST':
        name = request.form['name']
        bio = request.form['bio']
        conn = sqlite3.connect(DB_PATH)

        # Todo fix sql injection possibility here
        conn.execute(f"INSERT INTO People (name, bio) VALUES ('{name}', '{bio}')")
        conn.commit()
        return redirect(url_for('Index'))


# This route gives a page to add a child to a given parent, lets user choose who to add as a child
@app.route('/add_child/<id>', methods=['GET'])
def add_child(id):
    #if request.method == 'POST':
    conn = sqlite3.connect(DB_PATH)

    data = conn.execute(f'SELECT name FROM People WHERE id={id}').fetchone()
    person_name = data
    data = conn.execute(f'SELECT * FROM People WHERE id!={id}')

    return render_template('add_child.html', title='Add a child', person = person_name, parent_id = id, people=data)

# This route gives users the option to choose a parent to add to a selected node.
@app.route('/add_parent/<id>', methods=['GET'])
def add_parent(id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(f'SELECT name FROM People WHERE id={id}')
    data = cursor.fetchall()
    person_name = data[0]

    cursor = conn.execute(f'SELECT * FROM People WHERE id!={id}')
    data = cursor.fetchall()
    
    return render_template('add_parent.html', title='Add a parent', person = person_name, child_id = id, people=data)

# Add a parent/child edge to the SQL database
@app.route('/add_edge/<parent_id>/<child_id>', methods=['GET', 'POST'])
def add_edge(parent_id, child_id):
    print(f'edge ({parent_id}, {child_id})')
    conn = sqlite3.connect(DB_PATH)
    conn.execute(f"INSERT INTO Parents_Children (parent_id, child_id) VALUES ({parent_id}, {child_id})")
    conn.commit()
    return redirect(url_for('Index'))

@app.route('/edit_person/<id>', methods=['GET', 'POST'])
def edit_person(id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(f'SELECT * FROM People WHERE id={id}')
    data = cursor.fetchall()
    data = data[0]

    id, name, bio = data
    
    return render_template('edit_person.html', title='Edit a person', name=name, bio=bio, id=id)

@app.route('/update_person/<id>', methods=['GET', 'POST'])
def update_person(id):
    if request.method == 'POST':
        name = request.form['name']
        bio = request.form['bio']
        conn = sqlite3.connect(DB_PATH)

        cursor = conn.execute(f"UPDATE People SET name='{name}', bio='{bio}' WHERE id={id}")
        conn.commit()
        return redirect(url_for('Index'))

@app.route('/delete_person/<id>', methods=['GET', 'POST'])
def delete_person(id):
    # Delete the person and associated parent/child relationships
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute(f"DELETE FROM Parents_Children WHERE parent_id={id} OR child_id={id}")
        cursor = conn.execute(f"DELETE FROM People WHERE id={id}")
        conn.commit()
        return redirect('/')
    except Exception as e:
        print(e)
    finally:
        print(f"Requested node: {id} for deletion.")

@app.route('/delete_edge/<p_id>/<c_id>', methods=['GET', 'POST'])
def delete_edge(p_id, c_id):
    # Delete the edge with the matching parent and child IDs
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute(f'DELETE FROM Parents_Children WHERE parent_id={p_id} AND child_id={c_id}')
        conn.commit()
        return redirect('/')
    except Exception as e:
        print(e)
    finally:
        print(f"Requested edge: ({p_id}, {c_id}) for deletion.")

if __name__ == "__main__":
    app.run(port=57608, debug=True)