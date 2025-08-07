import os
from app_utils import load_dotenv
from chatlas import ChatGoogle
from shiny import App, ui, render, reactive
import pandas as pd
from pathlib import Path
import faicons as fa
import re

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

- Show me the data table

- What is the total bill?

- Show me the average tip percentage
                
- Filter for male smokers"""
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
        You are a helpful assistant that can control a user interface. 
        Based on the user's request, you can ask to show or hide UI elements.
        Use the following commands in your response to control the UI:
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
        - To hide specific elements: 'hide elements: [element1], [element2], ...' (e.g., 'hide elements: data table, total tippers')
        - To filter the data: 'filter: [column][operator][value]'. For multiple conditions, combine them with ' and ' (e.g., 'filter: sex=Male and smoker=Yes', 'filter: total_bill>20 and day=Thur')
        - Supported operators: =, >, <, >=, <=, ~
        - To clear filters: 'clear filters'
        - To remove a specific filter: 'remove filter: [column][operator][value]' (e.g., 'remove filter: sex=Male')
        """,
        model="gemini-2.0-flash",
    )

    chat = ui.Chat(id="chat")
    reactive_df = reactive.Value(df)
    active_ui_elements = reactive.Value(set())
    active_filters = reactive.Value([]) # New: To store active filter conditions

    @chat.on_user_submit
    async def handle_user_input(user_input: str):
        response_stream = await chat_client.stream_async(user_input)
        full_response = ""
        async for chunk in response_stream:
            full_response += chunk
        
        await chat.append_message(full_response)
        await process_commands(full_response.lower())

    async def process_commands(response_lower: str):
        commands = {
            "show data table": lambda: add_element("data_table", get_data_table_ui()),
            "hide data table": lambda: remove_element("data_table"),
            "show total tippers": lambda: add_element("total_tippers", get_total_tippers_ui()),
            "hide total tippers": lambda: remove_element("total_tippers"),
            "show total bill": lambda: add_element("total_bill", get_total_bill_ui()),
            "hide total bill": lambda: remove_element("total_bill"),
            "show average tip percentage": lambda: add_element("average_tip_percentage", get_average_tip_percentage_ui()),
            "hide average tip percentage": lambda: remove_element("average_tip_percentage"),
            "show average bill": lambda: add_element("average_bill", get_average_bill_ui()),
            "hide average bill": lambda: remove_element("average_bill"),
        }

        if "show everything" in response_lower:
            for cmd in ["show data table", "show total tippers", "show total bill", "show average tip percentage", "show average bill"]:
                commands[cmd]()
            return

        if "hide everything" in response_lower:
            for element_id in list(active_ui_elements()):
                remove_element(element_id)
            return

        if "hide elements:" in response_lower:
            elements_to_hide_str = response_lower.split("hide elements:")[1].strip()
            elements_to_hide = [e.strip() for e in elements_to_hide_str.split(',')]
            
            # Mapping user-friendly names to internal element IDs
            element_name_to_id = {
                "data table": "data_table",
                "total tippers": "total_tippers",
                "total bill": "total_bill",
                "average tip percentage": "average_tip_percentage",
                "average bill": "average_bill",
            }

            for element_name in elements_to_hide:
                element_id = element_name_to_id.get(element_name)
                if element_id:
                    remove_element(element_id)
            return

        if "filter:" in response_lower:
            filter_str_raw = response_lower.split("filter:")[1].strip()
            filter_conditions = [cond.strip() for cond in filter_str_raw.split(" and ")]
            
            current_filtered_df = df.copy() # Start with the original DataFrame for combined filtering

            for filter_condition in filter_conditions:
                try:
                    import re
                    match = re.match(r"([a-zA-Z_]+)([<>=~]+)(.*)", filter_condition)
                    if not match:
                        await chat.append_message(f"Invalid filter command format for '{filter_condition}'. Use 'filter: [column][operator][value]'")
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
                    else:
                        await chat.append_message(f"Unsupported operator: {operator}")
                        return

                except ValueError:
                    await chat.append_message(f"Invalid value for filtering in '{filter_condition}'. Please ensure numeric values are correct for comparisons.")
                    return
                except Exception as e:
                    await chat.append_message(f"An error occurred during filtering '{filter_condition}': {e}")
                    return
            
            reactive_df.set(current_filtered_df)
            await chat.append_message(f"Filtered data by '{filter_str_raw}'. Showing {len(current_filtered_df)} rows.")
            return

        if "clear filters" in response_lower:
            reactive_df.set(df)
            await chat.append_message("Filters cleared. Showing all data.")
            return

        for command, action in commands.items():
            if command in response_lower:
                action()

    def add_element(element_id: str, ui_element):
        if element_id not in active_ui_elements():
            ui.insert_ui(selector="#dynamic_ui_container", where="beforeEnd", ui=ui_element)
            active_ui_elements.set(active_ui_elements() | {element_id})

    def remove_element(element_id: str):
        if element_id in active_ui_elements():
            ui.remove_ui(selector=f"#{element_id}_wrapper")
            active_ui_elements.set(active_ui_elements() - {element_id})

    def get_data_table_ui():
        return ui.div(ui.h2("Data Table"), ui.output_data_frame("data_table"), id=f"data_table_wrapper")

    def get_total_tippers_ui():
        return ui.div(ui.value_box("Total tippers", ui.output_text("total_tippers"), showcase=fa.icon_svg("user", "regular")), id=f"total_tippers_wrapper")

    def get_total_bill_ui():
        return ui.div(ui.value_box("Total bill", ui.output_text("total_bill"), showcase=fa.icon_svg("dollar-sign")), id=f"total_bill_wrapper")

    def get_average_tip_percentage_ui():
        return ui.div(ui.value_box("Average tip percentage", ui.output_text("average_tip_percentage"), showcase=fa.icon_svg("percent")), id=f"average_tip_percentage_wrapper")

    def get_average_bill_ui():
        return ui.div(ui.value_box("Average bill", ui.output_text("average_bill"), showcase=fa.icon_svg("dollar-sign")), id=f"average_bill_wrapper")

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

app = App(app_ui, server)