import os
from app_utils import load_dotenv
from chatlas import ChatGoogle
from shiny import App, ui, render, reactive
import pandas as pd
import json
from pathlib import Path
import faicons as fa

# Data directory
here = Path(__file__).parent
tips = pd.read_csv(here / "tips.csv")
tips["percent"] = tips.tip / tips.total_bill
df = pd.DataFrame(tips)


app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.chat_ui(id="chat", messages=["Welcome!"], height="100%"),
        width=450, style="height:100%", title="Chat with Gemini"
    ),
    ui.page_fluid(
        ui.output_ui("total_tippers_ui"),
        ui.h2("Data Table"),
        ui.output_ui("dynamic_data_table_ui")
    )
)

def server(input, output, session):
    load_dotenv()
    chat_client = ChatGoogle(
        api_key=os.environ.get("GOOGLE_API_KEY"),
        system_prompt="You are a helpful assistant. When the user asks to see data, include the phrase 'show me data' in your response. When the user asks to hide data, include 'hide data' in your response. When the user asks for total tippers, include 'show total tippers' in your response.",
        model="gemini-2.0-flash",
    )

    chat = ui.Chat(id="chat")

    reactive_df = reactive.Value(df)
    show_df = reactive.Value(False)
    show_tippers = reactive.Value(False)

    @chat.on_user_submit
    async def handle_user_input(user_input: str):
        response_stream = await chat_client.stream_async(user_input)
        full_response = ""
        async for chunk in response_stream:
            full_response += chunk

        response_lower = full_response.lower()
        if "show me data" in response_lower:
            show_df.set(True)
        elif "hide data" in response_lower:
            show_df.set(False)
        elif "show total tippers" in response_lower:
            show_tippers.set(True)
        
        await chat.append_message(full_response)

    @render.ui
    def total_tippers_ui():
        if show_tippers():
            return ui.value_box(
                "Total tippers",
                ui.output_text("total_tippers"),
                showcase=fa.icon_svg("user", "regular"),
            )
        return None

    @render.text
    def total_tippers():
        return str(len(reactive_df()))

    @render.ui
    def dynamic_data_table_ui():
        if show_df():
            return ui.output_data_frame("data_table")
        return None

    @render.data_frame
    def data_table():
        return reactive_df()


app = App(app_ui, server)