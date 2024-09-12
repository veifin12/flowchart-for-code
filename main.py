import streamlit as st
from streamlit import session_state as state
import ast
import networkx as nx
import plotly.graph_objects as go
import textwrap
import pygraphviz as pgv
import base64
import io
import matplotlib.pyplot as plt
from streamlit_ace import st_ace

def get_preset_themes():
    return {
        "Default": {
            "bg_color": "#FFFFFF",
            "edge_color": "#888888",
            "font_color": "#000000",
            "function_color": "#3498db",
            "class_color": "#e67e22",
            "conditional_color": "#f1c40f",
            "loop_color": "#2ecc71",
            "try_except_color": "#e74c3c",
            "with_color": "#9b59b6",
            "other_color": "#95a5a6"
        },
        "Dark": {
            "bg_color": "#2c3e50",
            "edge_color": "#ecf0f1",
            "font_color": "#ecf0f1",
            "function_color": "#3498db",
            "class_color": "#e67e22",
            "conditional_color": "#f1c40f",
            "loop_color": "#2ecc71",
            "try_except_color": "#e74c3c",
            "with_color": "#9b59b6",
            "other_color": "#95a5a6"
        },
        "Pastel": {
            "bg_color": "#f0f0f0",
            "edge_color": "#95a5a6",
            "font_color": "#34495e",
            "function_color": "#93cfcf",
            "class_color": "#f7dc6f",
            "conditional_color": "#f0b27a",
            "loop_color": "#82e0aa",
            "try_except_color": "#f1948a",
            "with_color": "#bb8fce",
            "other_color": "#d5dbdb"
        }
    }

def parse_python_code(code):
    try:
        tree = ast.parse(code)
        return tree
    except SyntaxError as e:
        st.error(f"Syntax error in the provided code: {str(e)}")
        return None
    except Exception as e:
        st.error(f"An error occurred while parsing the code: {str(e)}")
        return None

def create_graph(tree):
    G = nx.DiGraph()
    node_id = 0
    def add_node(label, details, node_type):
        nonlocal node_id
        layer = max([G.nodes[n].get("layer", 0) for n in G.nodes()], default=-1) + 1
        G.add_node(node_id, label=label, details=details, node_type=node_type, layer=layer)
        current_id = node_id
        node_id += 1
        return current_id
    def process_node(node, parent_id=None):
        if isinstance(node, ast.FunctionDef):
            decorators = [ast.unparse(d) for d in node.decorator_list]
            decorator_str = f"@{', @'.join(decorators)}\n" if decorators else ""
            current_id = add_node(f"Function: {node.name}", f"{decorator_str}{ast.unparse(node)}", "function")
            if parent_id is not None:
                G.add_edge(parent_id, current_id)
            for item in node.body:
                process_node(item, current_id)
        elif isinstance(node, ast.ClassDef):
            decorators = [ast.unparse(d) for d in node.decorator_list]
            decorator_str = f"@{', @'.join(decorators)}\n" if decorators else ""
            current_id = add_node(f"Class: {node.name}", f"{decorator_str}{ast.unparse(node)}", "class")
            if parent_id is not None:
                G.add_edge(parent_id, current_id)
            for item in node.body:
                process_node(item, current_id)
        elif isinstance(node, ast.If):
            current_id = add_node("If", ast.unparse(node.test), "conditional")
            if parent_id is not None:
                G.add_edge(parent_id, current_id, label="True")
            for item in node.body:
                process_node(item, current_id)
            if node.orelse:
                else_id = add_node("Else", "", "conditional")
                G.add_edge(current_id, else_id, label="False")
                for item in node.orelse:
                    process_node(item, else_id)
        elif isinstance(node, ast.For):
            current_id = add_node("For loop", ast.unparse(node.target) + " in " + ast.unparse(node.iter), "loop")
            if parent_id is not None:
                G.add_edge(parent_id, current_id)
            for item in node.body:
                process_node(item, current_id)
        elif isinstance(node, ast.While):
            current_id = add_node("While loop", ast.unparse(node.test), "loop")
            if parent_id is not None:
                G.add_edge(parent_id, current_id)
            for item in node.body:
                process_node(item, current_id)
        elif isinstance(node, ast.Assign):
            current_id = add_node("Assignment", ast.unparse(node), "assignment")
            if parent_id is not None:
                G.add_edge(parent_id, current_id)
        elif isinstance(node, ast.Expr):
            if isinstance(node.value, ast.Call):
                current_id = add_node("Function call", ast.unparse(node), "function_call")
                if parent_id is not None:
                    G.add_edge(parent_id, current_id)
        elif isinstance(node, ast.Return):
            current_id = add_node("Return", ast.unparse(node), "return")
            if parent_id is not None:
                G.add_edge(parent_id, current_id)
        elif isinstance(node, ast.ListComp):
            current_id = add_node("List Comprehension", ast.unparse(node), "list_comp")
            if parent_id is not None:
                G.add_edge(parent_id, current_id)
        elif isinstance(node, ast.Try):
            current_id = add_node("Try", "", "try_except")
            if parent_id is not None:
                G.add_edge(parent_id, current_id)
            for item in node.body:
                process_node(item, current_id)
            for handler in node.handlers:
                except_id = add_node(f"Except: {ast.unparse(handler.type) if handler.type else 'all'}", "", "try_except")
                G.add_edge(current_id, except_id)
                for item in handler.body:
                    process_node(item, except_id)
        elif isinstance(node, ast.With):
            current_id = add_node("With", ast.unparse(node.items[0]), "with")
            if parent_id is not None:
                G.add_edge(parent_id, current_id)
            for item in node.body:
                process_node(item, current_id)
    for item in tree.body:
        process_node(item)
    return G

def create_plotly_diagram(G, node_color_scheme, edge_color, node_size, edge_width, font_size, font_color, bg_color, layout_direction, function_color, class_color, conditional_color, loop_color, try_except_color, with_color, other_color, large_text_threshold, large_text_color, large_text_size):
    layout_args = '-Grankdir=TB' if layout_direction == "Top to Bottom" else '-Grankdir=LR'
    pos = nx.nx_agraph.graphviz_layout(G, prog='dot', args=layout_args)
    edge_x = []
    edge_y = []
    edge_text = []
    for edge in G.edges(data=True):
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])
        if 'label' in edge[2]:
            edge_text.extend([edge[2]['label'], edge[2]['label'], None])
        else:
            edge_text.extend([None, None, None])
    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=edge_width, color=edge_color),
        hoverinfo='none',
        mode='lines+text',
        text=edge_text,
        textposition='middle center',
        textfont=dict(size=10, color='black'))
    node_x = []
    node_y = []
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
    node_colors = []
    for node in G.nodes():
        node_type = G.nodes[node]['node_type']
        if node_type == 'function':
            node_colors.append(function_color)
        elif node_type == 'class':
            node_colors.append(class_color)
        elif node_type == 'conditional':
            node_colors.append(conditional_color)
        elif node_type == 'loop':
            node_colors.append(loop_color)
        elif node_type == 'try_except':
            node_colors.append(try_except_color)
        elif node_type == 'with':
            node_colors.append(with_color)
        else:
            node_colors.append(other_color)
    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        hoverinfo='text',
        marker=dict(
            showscale=False,
            size=node_size,
            color=node_colors,
            line=dict(width=2, color='black')),
        textfont=dict(size=font_size, color=font_color))
    node_labels = []
    node_details = []
    node_symbols = []
    for node in G.nodes():
        node_labels.append(G.nodes[node]['label'])
        node_details.append(G.nodes[node]['details'])
        node_type = G.nodes[node]['node_type']
        if node_type == 'function':
            node_symbols.append('square')
        elif node_type == 'class':
            node_symbols.append('hexagon')
        elif node_type == 'conditional':
            node_symbols.append('diamond')
        elif node_type == 'loop':
            node_symbols.append('circle')
        elif node_type == 'try_except':
            node_symbols.append('octagon')
        elif node_type == 'with':
            node_symbols.append('star')
        else:
            node_symbols.append('circle')
    node_trace.marker.symbol = node_symbols
    
    node_text = []
    node_text_color = []
    node_text_size = []
    for label in node_labels:
        wrapped_text = '<br>'.join(textwrap.wrap(label, width=15))
        node_text.append(wrapped_text)
        if len(label) > large_text_threshold:
            node_text_color.append(large_text_color)
            node_text_size.append(large_text_size)
        else:
            node_text_color.append(font_color)
            node_text_size.append(font_size)
    
    node_trace.text = node_text
    node_trace.textfont = dict(color=node_text_color, size=node_text_size)
    node_trace.hovertext = [details.replace('\n', '<br>') for details in node_details]
    
    fig = go.Figure(data=[edge_trace, node_trace],
                    layout=go.Layout(
                        showlegend=False,
                        hovermode='closest',
                        margin=dict(b=20, l=5, r=5, t=40),
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        width=1200,
                        height=800,
                        plot_bgcolor=bg_color,
                        paper_bgcolor=bg_color
                    ))
    return fig

def export_diagram(fig, format='png'):
    try:
        print(f"Exporting diagram in {format} format")
        print(f"Fig object: {fig}")
        img_bytes = fig.to_image(format=format)
        print(f"Export successful, image size: {len(img_bytes)} bytes")
        return img_bytes
    except Exception as e:
        print(f"Error exporting diagram: {str(e)}")
        st.error(f"Error exporting diagram: {str(e)}")
        return None

def main():
    st.set_page_config(page_title="Python Code to Flowchart Converter", layout="wide")
    st.title("Python Code to Flowchart Converter")

    st.sidebar.header("How to Use")
    st.sidebar.markdown("""
    1. Enter your Python code in the code editor.
    2. Click the 'Generate Flowchart' button.
    3. The flowchart will appear below the input area.
    4. Hover over nodes to see more details about the code.
    5. Click and drag to pan the diagram.
    6. Scroll to zoom in and out.
    7. Double-click to reset the view.
    8. Use the export options to download the diagram.
    """)

    # Add theme options
    st.sidebar.header("Theme Options")
    preset_themes = get_preset_themes()
    selected_theme = st.sidebar.selectbox("Select Theme", list(preset_themes.keys()) + ["Custom"])
    
    if selected_theme != "Custom":
        theme = preset_themes[selected_theme]
        bg_color = theme["bg_color"]
        edge_color = theme["edge_color"]
        font_color = theme["font_color"]
        function_color = theme["function_color"]
        class_color = theme["class_color"]
        conditional_color = theme["conditional_color"]
        loop_color = theme["loop_color"]
        try_except_color = theme["try_except_color"]
        with_color = theme["with_color"]
        other_color = theme["other_color"]
    else:
        # Add custom theme options
        st.sidebar.header("Customize Flowchart")
        bg_color = st.sidebar.color_picker("Background Color", "#FFFFFF")
        edge_color = st.sidebar.color_picker("Edge Color", "#888")
        font_color = st.sidebar.color_picker("Font Color", "#000000")
        
        st.sidebar.subheader("Node Colors")
        function_color = st.sidebar.color_picker("Function Color", "#3498db")
        class_color = st.sidebar.color_picker("Class Color", "#e67e22")
        conditional_color = st.sidebar.color_picker("Conditional Color", "#f1c40f")
        loop_color = st.sidebar.color_picker("Loop Color", "#2ecc71")
        try_except_color = st.sidebar.color_picker("Try/Except Color", "#e74c3c")
        with_color = st.sidebar.color_picker("With Statement Color", "#9b59b6")
        other_color = st.sidebar.color_picker("Other Statement Color", "#95a5a6")

    node_color_scheme = st.sidebar.selectbox("Node Color Scheme", 
                                             ["Viridis", "Plasma", "Inferno", "Magma", "Cividis"])
    node_size = st.sidebar.slider("Node Size", 10, 50, 20)
    edge_width = st.sidebar.slider("Edge Width", 1, 10, 2)
    font_size = st.sidebar.slider("Font Size", 8, 20, 14)
    layout_direction = st.sidebar.selectbox("Layout Direction", ["Top to Bottom", "Left to Right"])

    st.sidebar.subheader("Large Text Customization")
    large_text_threshold = st.sidebar.slider("Large Text Threshold (characters)", 10, 50, 20)
    large_text_color = st.sidebar.color_picker("Large Text Color", "#FF0000")
    large_text_size = st.sidebar.slider("Large Text Size", 8, 24, 12)

    if st.sidebar.button("Save Current Theme"):
        current_theme = {
            "bg_color": bg_color,
            "edge_color": edge_color,
            "font_color": font_color,
            "function_color": function_color,
            "class_color": class_color,
            "conditional_color": conditional_color,
            "loop_color": loop_color,
            "try_except_color": try_except_color,
            "with_color": with_color,
            "other_color": other_color
        }
        theme_name = st.sidebar.text_input("Enter a name for your theme:")
        if theme_name:
            preset_themes[theme_name] = current_theme
            st.sidebar.success(f"Theme '{theme_name}' saved successfully!")

    # Replace st.text_area with st_ace for syntax highlighting
    code = st_ace(
        placeholder="Enter your Python code here",
        language="python",
        theme="monokai",
        keybinding="vscode",
        font_size=14,
        tab_size=4,
        show_gutter=True,
        show_print_margin=False,
        wrap=True,
        auto_update=True,
        height=300
    )

    if st.button("Generate Flowchart"):
        if code:
            tree = parse_python_code(code)
            if tree:
                graph = create_graph(tree)
                state.fig = create_plotly_diagram(graph, node_color_scheme.lower(), edge_color, node_size, edge_width, font_size, font_color, bg_color, layout_direction, function_color, class_color, conditional_color, loop_color, try_except_color, with_color, other_color, large_text_threshold, large_text_color, large_text_size)
                
                st.subheader("Diagram Legend")
                st.write("- Blue squares: Functions")
                st.write("- Orange hexagons: Classes")
                st.write("- Yellow diamonds: Conditionals (If/Else)")
                st.write("- Green circles: Loops")
                st.write("- Red octagons: Try/Except blocks")
                st.write("- Purple stars: With statements")
                st.write("- Gray circles: Other statements")
                st.write("- Edge labels: 'True' and 'False' for conditional branches")
        else:
            st.warning("Please enter some Python code to generate a flowchart.")

    # Display the chart if it exists in the state
    if 'fig' in state:
        st.plotly_chart(state.fig, use_container_width=True)

    # Add export options
    st.subheader("Export Diagram")
    with st.form("export_form"):
        export_format = st.selectbox("Select export format", ["PNG", "SVG"])
        export_button = st.form_submit_button("Export Diagram")
        
    if export_button:
        if 'fig' in state:
            file_extension = export_format.lower()
            exported_diagram = export_diagram(state.fig, format=file_extension)
            if exported_diagram:
                filename = f"flowchart.{file_extension}"
                st.download_button(
                    label=f"Download {export_format}",
                    data=exported_diagram,
                    file_name=filename,
                    mime=f"image/{file_extension}"
                )
        else:
            st.warning("Please generate a flowchart first before exporting.")

if __name__ == "__main__":
    main()
