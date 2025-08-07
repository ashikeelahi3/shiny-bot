# ------------------------------------------------------------------------------------
# A basic Shiny Chat example powered by Google's Gemini model.
# ------------------------------------------------------------------------------------
import os
from app_utils import load_dotenv
from chatlas import ChatGoogle
from shiny import App, ui, render, reactive
import pandas as pd
import json

# Sample data
initial_df = pd.DataFrame({
    'Name': ['Alice', 'Bob', 'Charlie'],
    'Age': [25, 30, 35],
    'City': ['NYC', 'LA', 'Chicago']
})

load_dotenv()
chat_client = ChatGoogle(
    api_key=os.environ.get("GOOGLE_API_KEY"),
    system_prompt="You are a helpful assistant.",
    model="gemini-2.0-flash",
)

app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.chat_ui(id="chat", messages=["Welcome!"], height="100%"),
        width=450, style="height:100%", title="Chat with Gemini"
    ),
    ui.page_fluid(
        ui.input_file("f", "Pick a file, CSV or Excel", accept=[".csv", ".xlsx"], multiple=False),
        "Input file data:",
        # ui.output_text("json_data"),  # Placeholder for JSON data
    ),
    ui.page_fluid(
        ui.h2("Data Table"),
        ui.output_data_frame("data_table")
    )
)

def server(input, output, session):
    chat = ui.Chat(id="chat")
    # chat.enable_bookmarking(
    #     chat_client,
    # )
    # chat.enable_bookmarking(chat_client, bookmark_store="server")

    reactive_df = reactive.Value(initial_df)

    @chat.on_user_submit
    async def handle_user_input(user_input: str):
        response = await chat_client.stream_async(user_input)
        await chat.append_message_stream(response)

    @reactive.Effect
    @reactive.event(input.f)
    def _():
        file = input.f()
        if not file:
            return
        
        file_info = file[0]
        path = file_info["datapath"]
        name = file_info["name"].lower()
        
        try:
            if name.endswith('.csv'):
                new_df = pd.read_csv(path)
            else:
                new_df = pd.read_excel(path)
            reactive_df.set(new_df)
        except Exception as e:
            ui.notification_show(f"Error: {e}", duration=5, type="error")

    @render.data_frame
    def data_table():
        return reactive_df()
    
    # @render.text
    # def json_data():
    #     df = reactive_df()
    #     return json.dumps(df.to_dict('records'), indent=2)


app = App(app_ui, server)