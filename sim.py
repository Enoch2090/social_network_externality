import streamlit as st
import networkx as nx
import numpy as np
import random
import math
import pandas as pd
import altair as alt
import nx_altair as nxa

# Set the seed for reproducibility
random.seed(42)
np.random.seed(42)

MAX_TIME = 20
GLOBAL_GRAPH = {
    'Grid': {
        'func': nx.grid_2d_graph,
        'pos': lambda G: {(x, y): (x, y)  for (x, y) in G.nodes}
    },
    'Barabasi-Albert': {
        'func': nx.barabasi_albert_graph,
        'pos': lambda G: nx.spring_layout(G, k=0.15, iterations=20)
    }
}

alt.data_transformers.disable_max_rows()
st.session_state['timesteps'] = 1
st.session_state['node_data'] = []
st.session_state['edge_data'] = []
st.session_state['percentage'] = []

# Define the functions
def g1(network_size):
    return math.log(1 + network_size)

def g2(known_people):
    return math.log(1 + known_people)

def g3(platform_subsidy):
    return platform_subsidy

def get_viz(node_data, edge_data, percentage):
    df = pd.DataFrame(node_data)
    slider = alt.binding_range(min=0, max=MAX_TIME-1, step=1, name='Timestep:')
    slider_selection = alt.selection_single(name="timestep_selector", fields=['timestep'], bind=slider, init={'timestep': 0})

    # Create an Altair chart with the nodes and edges
    node_chart = alt.Chart(df).mark_circle(size=150).encode(
        x=alt.X('x:Q'),
        y=alt.Y('y:Q'),
        color=alt.condition(slider_selection, 'color:N', alt.value('blue'), legend=None),
        opacity=alt.condition(slider_selection, alt.value(1), alt.value(0.))
    ).add_selection(
        slider_selection
    ).properties(width=600, height=600)

    edge_df = pd.DataFrame(edge_data)
    edge_chart = alt.Chart(edge_df).mark_line().encode(
        x='x1',
        y='y1',
        x2='x2',
        y2='y2'
    ).properties(width=600, height=600)

    percentage_chart = alt.Chart(pd.DataFrame(percentage)).mark_line().encode(
        x='timestep:Q',
        y='Percentage:Q'
    ).properties(width=600, height=400)
    
    chart = (percentage_chart & (edge_chart + node_chart)).configure_axis(grid=False, domain=False)
    return chart

def main():
    st.title('Social Network Simulation')
    st.sidebar.markdown('# Graph Settings')
    graph_type = st.sidebar.selectbox('Select Graph Type', ['Grid', 'Barabasi-Albert'])
    st.sidebar.markdown('## Graph Kwargs')
    if graph_type == 'Grid':
        graph_grid_size = st.sidebar.number_input('Grid Size', value=32)
        graph_kwargs = {
            'm': graph_grid_size,
            'n': graph_grid_size
        }
    elif graph_type == 'Barabasi-Albert':
        graph_node_num = st.sidebar.number_input('Number of Nodes', value=324)
        graph_edge_attach = st.sidebar.number_input('Number of Edges to Attach', value=2)
        graph_kwargs = {
            'n': graph_node_num,
            'm': graph_edge_attach,
            'seed': 42
        }

    G = GLOBAL_GRAPH[graph_type]['func'](**graph_kwargs)
    layout_func = GLOBAL_GRAPH[graph_type]['pos']
    st.sidebar.markdown('# Platform & User Settings')
    w1 = st.sidebar.slider('Weight for network size (w1)', 0.0, 1.0, 1.0)
    w2 = st.sidebar.slider('Weight for known people (w2)', 0.0, 1.0, 1.0)
    w3 = st.sidebar.slider('Weight for platform subsidy (w3)', 0.0, 1.0, 1.0)
    subsidy = st.sidebar.slider('Platform subsidy', 0, 15, 10)
    transition_lb = st.sidebar.number_input('Transition cost lowerbound', value=10)
    transition_ub = st.sidebar.number_input('Transition cost upperbound', value=20)

    # Slider for bootstrap
    bootstrap = st.sidebar.slider('Bootstrap', 0.0, 1.0, 0.15)

    # Simulation button
    simulate = st.sidebar.button('Simulate')
    
    if simulate:
        with st.spinner():
            st.session_state['timesteps'], st.session_state['node_data'], st.session_state['edge_data'], st.session_state['percentage'] = run_simulation(G, layout_func, w1, w2, w3, subsidy, transition_lb, transition_ub, bootstrap)
    try:
        chart = get_viz(st.session_state['node_data'], st.session_state['edge_data'], st.session_state['percentage'])
        st.altair_chart(chart)
    except Exception as e:
        # print(e)
        st.text('Run simulation first')

def run_simulation(G, layout_func, w1, w2, w3, subsidy, transition_lb, transition_ub, bootstrap):
    for node in G.nodes:
        G.nodes[node]['on_platform'] = False
        G.nodes[node]['transition_cost'] = random.uniform(transition_lb, transition_ub)

    num_initial_nodes = int(bootstrap * len(G.nodes))
    
    layout = layout_func(G)
    
    # Set the seed for reproducibility
    random.seed(42)
    initial_nodes = random.sample(list(G.nodes), num_initial_nodes)
    for node in initial_nodes:
        G.nodes[node]['on_platform'] = True

    timesteps = MAX_TIME
    node_data = []
    percentage = [{'Percentage': bootstrap, 'timestep': 0}]
    edge_data = []
    for edge in G.edges:
        edge_data.append({'x1': layout[edge[0]][0], 'y1': layout[edge[0]][1], 'x2': layout[edge[1]][0], 'y2': layout[edge[1]][1]})
        
    for node in G.nodes:
        color = 'red' if G.nodes[node]['on_platform'] else 'blue'
        node_data.append({'x': layout[node][0], 'y': layout[node][1], 'timestep': 0, 'color': color})
        
    network_size = len([n for n in G.nodes(data=True) if n[1]['on_platform']])
    for t in range(timesteps - 1):
        for node in G.nodes:
            G.nodes[node]['known_people'] = len([n for n in G.neighbors(node) if G.nodes(data=True)[n]['on_platform']])
        for node in G.nodes:
            G.nodes[node]['known_people'] = len([n for n in G.neighbors(node) if G.nodes(data=True)[n]['on_platform']])
            
            U = (
                w1 * g1(network_size) +
                w2 * g2(G.nodes[node]['known_people']) +
                w3 * g3(subsidy)
            )

            if U > G.nodes[node]['transition_cost']:
                G.nodes[node]['on_platform'] = True
                G.nodes[node]['transition_cost'] = 0
            else:
                G.nodes[node]['on_platform'] = False
                
            color = 'red' if G.nodes[node]['on_platform'] else 'blue'
            node_data.append({'x': layout[node][0], 'y': layout[node][1], 'timestep': t + 1, 'color': color})
        network_size = len([n for n in G.nodes(data=True) if n[1]['on_platform']])
        percentage.append({'Percentage': network_size / len(G.nodes), 'timestep': t + 1})
    return timesteps, node_data, edge_data, percentage

if __name__ == "__main__":
    main()