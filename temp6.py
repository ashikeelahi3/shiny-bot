import os
from app_utils import load_dotenv
from chatlas import ChatGoogle
from shiny import App, ui, render, reactive
import pandas as pd
from pathlib import Path
import faicons as fa
import re
import plotly.express as px
import plotly.graph_objects as go
from shinywidgets import output_widget, render_widget

# Data directory
here = Path(__file__).parent
tips = pd.read_csv(here / "tips.csv")
tips["percent"] = tips.tip / tips.total_bill
df = pd.DataFrame(tips)

app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.chat_ui(id="chat", messages=[
            """Welcome to the Shiny App! I can help you analyze the tippers dataset. What would you like to see? 
            Here are some suggestions:

**Data Analysis:**
- Show me the data table
- What is the total bill?
- Show me the average tip percentage
- Filter for male smokers

**Visualizations:**
- Show histogram of total_bill
- Create scatter plot of total_bill vs tip
- Show bar chart of day counts
- Plot tip percentage by sex and smoker
- Show box plot of total_bill by day
- Create heatmap of average tip by day and time
                
Available columns: total_bill, tip, sex, smoker, day, time, size, percent"""
            ], height="100%"),
        width=450, style="height:100%", title="Chat with Gemini"
    ),
    ui.page_fluid(
        ui.div(id="dynamic_ui_container")
    )
)

def server(input, output, session):
    load_dotenv()
    chat_client = ChatGoogle(
        api_key=os.environ.get("GOOGLE_API_KEY"),
        system_prompt="""
        You are a helpful assistant that can control a user interface and create data visualizations. 
        Based on the user's request, you can show/hide UI elements and create plots.
        
        **UI Control Commands:**
        - To show the data table: 'show data table'
        - To hide the data table: 'hide data table'
        - To show the total number of tippers: 'show total tippers'
        - To hide the total number of tippers: 'hide total tippers'
        - To show the total bill: 'show total bill'
        - To hide the total bill: 'hide total bill'
        - To show the average tip percentage: 'show average tip percentage'
        - To hide the average tip percentage: 'hide average tip percentage'
        - To show the average bill: 'show average bill'
        - To hide the average bill: 'hide average bill'
        - To show everything: 'show everything'
        - To hide everything: 'hide everything'
        - To hide specific elements: 'hide elements: [element1], [element2], ...'
        
        **Filtering Commands:**
        - To filter the data: 'filter: [column][operator][value]' (e.g., 'filter: sex=Male and smoker=Yes')
        - Supported operators: =, >, <, >=, <=, ~
        - To clear filters: 'clear filters'
        
        **Plot Commands:**
        - Histogram: 'plot histogram: [column]' (e.g., 'plot histogram: total_bill')
        - Bar chart: 'plot bar: [column]' (e.g., 'plot bar: day')
        - Scatter plot: 'plot scatter: [x_column] vs [y_column]' (e.g., 'plot scatter: total_bill vs tip')
        - Box plot: 'plot box: [column] by [group_column]' (e.g., 'plot box: total_bill by day')
        - Line plot: 'plot line: [x_column] vs [y_column]' (e.g., 'plot line: size vs tip')
        - Violin plot: 'plot violin: [column] by [group_column]' (e.g., 'plot violin: tip by smoker')
        - Heatmap: 'plot heatmap: [value_column] by [x_column] and [y_column]' (e.g., 'plot heatmap: tip by day and time')
        - To hide plots: 'hide plot'
        
        Available columns: total_bill, tip, sex, smoker, day, time, size, percent
        
        When users ask for visualizations, suggest appropriate plot types and variables based on their request.
        """,
        model="gemini-2.0-flash",
    )

    chat = ui.Chat(id="chat")
    reactive_df = reactive.Value(df)
    active_ui_elements = reactive.Value(set())
    current_plot = reactive.Value(None)
    current_plot_config = reactive.Value(None)  # Store plot configuration for updates

    @chat.on_user_submit
    async def handle_user_input(user_input: str):
        response_stream = await chat_client.stream_async(user_input)
        full_response = ""
        async for chunk in response_stream:
            full_response += chunk
        
        await chat.append_message(full_response)
        await process_commands(full_response.lower())

    async def process_commands(response_lower: str):
        value_box_details = {
            "total_tippers": {"title": "Total tippers", "icon": "user"},
            "total_bill": {"title": "Total bill", "icon": "dollar-sign"},
            "average_tip_percentage": {"title": "Average tip percentage", "icon": "percent"},
            "average_bill": {"title": "Average bill", "icon": "dollar-sign"},
        }

        commands = {
            "show data table": lambda: add_element("data_table", get_ui_element("data_table")),
            "hide data table": lambda: remove_element("data_table"),
            **{f"show {key.replace('_', ' ')}": lambda key=key: add_element(key, get_ui_element("value_box", title=value_box_details[key]["title"], output_id=key, icon_name=value_box_details[key]["icon"])) for key in value_box_details},
            **{f"hide {key.replace('_', ' ')}": lambda key=key: remove_element(key) for key in value_box_details},
        }

        # Handle show/hide everything
        if "show everything" in response_lower:
            for cmd_key in value_box_details.keys():
                commands[f"show {cmd_key.replace('_', ' ')}"]()
            commands["show data table"]()
            return

        if "hide everything" in response_lower:
            for element_id in list(active_ui_elements()):
                remove_element(element_id)
            return

        # Handle hide specific elements
        if "hide elements:" in response_lower:
            elements_to_hide_str = response_lower.split("hide elements:")[1].strip()
            elements_to_hide = [e.strip() for e in elements_to_hide_str.split(',')]
            
            element_name_to_id = {
                "data table": "data_table",
                **{key.replace('_', ' '): key for key in value_box_details.keys()}
            }

            for element_name in elements_to_hide:
                element_id = element_name_to_id.get(element_name)
                if element_id:
                    remove_element(element_id)
            return

        # Handle plotting commands
        if "plot histogram:" in response_lower:
            column = response_lower.split("plot histogram:")[1].strip()
            await create_plot("histogram", x=column)
            return

        if "plot bar:" in response_lower:
            column = response_lower.split("plot bar:")[1].strip()
            await create_plot("bar", x=column)
            return

        if "plot scatter:" in response_lower:
            vars_str = response_lower.split("plot scatter:")[1].strip()
            if " vs " in vars_str:
                x_col, y_col = [v.strip() for v in vars_str.split(" vs ")]
                await create_plot("scatter", x=x_col, y=y_col)
            return

        if "plot box:" in response_lower:
            vars_str = response_lower.split("plot box:")[1].strip()
            if " by " in vars_str:
                y_col, x_col = [v.strip() for v in vars_str.split(" by ")]
                await create_plot("box", x=x_col, y=y_col)
            return

        if "plot line:" in response_lower:
            vars_str = response_lower.split("plot line:")[1].strip()
            if " vs " in vars_str:
                x_col, y_col = [v.strip() for v in vars_str.split(" vs ")]
                await create_plot("line", x=x_col, y=y_col)
            return

        if "plot violin:" in response_lower:
            vars_str = response_lower.split("plot violin:")[1].strip()
            if " by " in vars_str:
                y_col, x_col = [v.strip() for v in vars_str.split(" by ")]
                await create_plot("violin", x=x_col, y=y_col)
            return

        if "plot heatmap:" in response_lower:
            vars_str = response_lower.split("plot heatmap:")[1].strip()
            if " by " in vars_str and " and " in vars_str:
                parts = vars_str.split(" by ", 1)[1]
                if " and " in parts:
                    value_col = vars_str.split(" by ")[0].strip()
                    x_col, y_col = [v.strip() for v in parts.split(" and ")]
                    await create_plot("heatmap", x=x_col, y=y_col, z=value_col)
            return

        if "hide plot" in response_lower:
            remove_element("plot")
            return

        # Handle filtering
        if "filter:" in response_lower:
            filter_str_raw = response_lower.split("filter:")[1].strip()
            filter_conditions = [cond.strip() for cond in filter_str_raw.split(" and ")]
            
            current_filtered_df = df.copy()

            for filter_condition in filter_conditions:
                try:
                    match = re.match(r"([a-zA-Z_]+)([<>=~]+)(.*)", filter_condition)
                    if not match:
                        await chat.append_message(f"Invalid filter command format for '{filter_condition}'.")
                        return

                    column, operator, value = match.groups()
                    column = column.strip()
                    value = value.strip()

                    if column not in current_filtered_df.columns:
                        await chat.append_message(f"Column '{column}' not found.")
                        return

                    if operator == "=":
                        if pd.api.types.is_numeric_dtype(current_filtered_df[column]):
                            current_filtered_df = current_filtered_df[current_filtered_df[column] == float(value)]
                        else:
                            current_filtered_df = current_filtered_df[current_filtered_df[column].astype(str).str.lower() == value.lower()]
                    elif operator == ">":
                        current_filtered_df = current_filtered_df[current_filtered_df[column] > float(value)]
                    elif operator == "<":
                        current_filtered_df = current_filtered_df[current_filtered_df[column] < float(value)]
                    elif operator == ">=":
                        current_filtered_df = current_filtered_df[current_filtered_df[column] >= float(value)]
                    elif operator == "<=":
                        current_filtered_df = current_filtered_df[current_filtered_df[column] <= float(value)]
                    elif operator == "~":
                        current_filtered_df = current_filtered_df[current_filtered_df[column].astype(str).str.lower().str.contains(value.lower())]

                except ValueError:
                    await chat.append_message(f"Invalid value for filtering in '{filter_condition}'.")
                    return
                except Exception as e:
                    await chat.append_message(f"Error during filtering '{filter_condition}': {e}")
                    return
            
            reactive_df.set(current_filtered_df)
            await chat.append_message(f"Filtered data by '{filter_str_raw}'. Showing {len(current_filtered_df)} rows.")
            return

        if "clear filters" in response_lower:
            reactive_df.set(df)
            await chat.append_message("Filters cleared. Showing all data.")
            return

        # Execute other commands
        for command, action in commands.items():
            if command in response_lower:
                action()

    async def create_plot(plot_type: str, x: str = None, y: str = None, z: str = None):
        data = reactive_df()
        
        if data.empty:
            await chat.append_message("No data available for plotting.")
            return
        
        # Validate columns
        available_cols = data.columns.tolist()
        for col in [x, y, z]:
            if col and col not in available_cols:
                await chat.append_message(f"Column '{col}' not found. Available columns: {', '.join(available_cols)}")
                return

        # Store plot configuration for reactive updates
        plot_config = {"type": plot_type, "x": x, "y": y, "z": z}
        current_plot_config.set(plot_config)

        try:
            fig = create_plot_figure(data, plot_config)
            current_plot.set(fig)
            add_element("plot", get_ui_element("plot"))
            await chat.append_message(f"Created {plot_type} plot successfully!")
            
        except Exception as e:
            await chat.append_message(f"Error creating plot: {e}")

    def create_plot_figure(data, plot_config):
        """Helper function to create plot figure from data and config"""
        plot_type = plot_config["type"]
        x = plot_config["x"]
        y = plot_config["y"] 
        z = plot_config["z"]
        
        if plot_type == "histogram" and x:
            return px.histogram(data, x=x, title=f"Histogram of {x}")
        elif plot_type == "bar" and x:
            value_counts = data[x].value_counts()
            return px.bar(x=value_counts.index, y=value_counts.values, 
                       labels={'x': x, 'y': 'Count'}, title=f"Bar Chart of {x}")
        elif plot_type == "scatter" and x and y:
            return px.scatter(data, x=x, y=y, title=f"Scatter Plot: {x} vs {y}")
        elif plot_type == "box" and x and y:
            return px.box(data, x=x, y=y, title=f"Box Plot: {y} by {x}")
        elif plot_type == "line" and x and y:
            return px.line(data, x=x, y=y, title=f"Line Plot: {x} vs {y}")
        elif plot_type == "violin" and x and y:
            return px.violin(data, x=x, y=y, title=f"Violin Plot: {y} by {x}")
        elif plot_type == "heatmap" and x and y and z:
            # Create pivot table for heatmap
            pivot_data = data.groupby([x, y])[z].mean().unstack(fill_value=0)
            return px.imshow(pivot_data, title=f"Heatmap: {z} by {x} and {y}")
        else:
            raise ValueError(f"Invalid plot configuration for {plot_type}.")

    def add_element(element_id: str, ui_element):
        if element_id not in active_ui_elements():
            ui.insert_ui(selector="#dynamic_ui_container", where="beforeEnd", ui=ui_element)
            active_ui_elements.set(active_ui_elements() | {element_id})

    def remove_element(element_id: str):
        if element_id in active_ui_elements():
            ui.remove_ui(selector=f"#{element_id}_wrapper")
            active_ui_elements.set(active_ui_elements() - {element_id})

    def get_ui_element(element_type: str, **kwargs):
        if element_type == "data_table":
            return ui.div(ui.h2("Data Table"), ui.output_data_frame("data_table"), id="data_table_wrapper")
        elif element_type == "value_box":
            output_id = kwargs.get("output_id") or ""
            icon_name = kwargs.get("icon_name") or ""
            return ui.div(
                ui.value_box(
                    kwargs.get("title"),
                    ui.output_text(output_id),
                    showcase=fa.icon_svg(icon_name)
                ),
                id=f"{output_id}_wrapper"
            )
        elif element_type == "plot":
            return ui.div(ui.h2("Visualization"), output_widget("plot_output"), id="plot_wrapper")

    # Render functions
    @render.data_frame
    def data_table():
        return reactive_df()

    @render.text
    def total_tippers():
        return str(len(reactive_df()))

    @render.text
    def total_bill():
        return f"${reactive_df()['total_bill'].sum():,.2f}"

    @render.text
    def average_tip_percentage():
        return f"{reactive_df()['percent'].mean():.2%}"

    @render.text
    def average_bill():
        return f"${reactive_df()['total_bill'].mean():,.2f}"

    @render_widget
    def plot_output():
        # Reactive plot that updates when data or plot config changes
        data = reactive_df()
        config = current_plot_config()
        
        if config and not data.empty:
            try:
                return create_plot_figure(data, config)
            except:
                return None
        return current_plot()

app = App(app_ui, server)