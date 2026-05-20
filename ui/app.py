import gradio as gr
import requests

BACKEND_URL = "http://localhost:8000/predict"

# ──────────────────────────────────────────────
# Lógica de llamada al backend
# ──────────────────────────────────────────────

def chat(user_message: str, history: list):
    if not user_message.strip():
        return history, "", "⚠️ Escribe un mensaje antes de enviar."

    payload = {
        "input": user_message,
        "history": [{"role": "user" if i % 2 == 0 else "assistant", "content": m}
                    for i, (u, a) in enumerate(history) for m in [u, a] if m],
        "options": {"temperature": 0.2, "max_tokens": 256}
    }

    try:
        response = requests.post(BACKEND_URL, json=payload, timeout=10)
        data = response.json()

        if data.get("ok"):
            mock_tag = " *(mock)*" if data.get("meta", {}).get("mock") else ""
            bot_reply = f"{data['output']}{mock_tag}"
            error_msg = ""
        else:
            error = data.get("error", {})
            bot_reply = "Lo siento, no he podido procesar tu consulta."
            error_msg = f"❌ {error.get('message', 'Error desconocido')} [{error.get('code', '')}]"

    except requests.exceptions.ConnectionError:
        bot_reply = ""
        error_msg = "❌ No se puede conectar con el servidor. ¿Está el backend en marcha?"
    except Exception as e:
        bot_reply = ""
        error_msg = f"❌ Error inesperado: {str(e)}"

    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": bot_reply})
    return history, "", error_msg


# ──────────────────────────────────────────────
# Interfaz Gradio (compatible con Gradio 5+)
# ──────────────────────────────────────────────

css = """
    .header { text-align: center; padding: 16px 0 8px 0; }
    .header h1 { font-size: 1.6em; color: #2D2D2D; margin: 0; }
    .header p  { color: #888; margin: 4px 0 0 0; font-size: 0.9em; }
    .error-box { color: #c0392b; font-size: 0.88em; min-height: 24px; }
    footer { display: none !important; }
"""

with gr.Blocks(title="TorresMack — Asistente de Seguros") as demo:

    gr.HTML("""
        <div class="header" style="text-align:center; padding: 16px 0 8px 0;">
            <h1 style="font-size:1.6em; color:#2D2D2D; margin:0;">
                🎭 TorresMack · Asistente de Seguros
            </h1>
            <p style="color:#888; margin:4px 0 0 0; font-size:0.9em;">
                Consulta sobre seguros de coche, hogar y artes escénicas
            </p>
        </div>
    """)

    chatbot = gr.Chatbot(
        label="Conversación",
        height=420,
    )

    with gr.Row():
        txt_input = gr.Textbox(
            placeholder="Escribe tu consulta aquí... (ej: ¿Qué cubre el seguro de hogar?)",
            show_label=False,
            scale=5,
            lines=1,
        )
        btn_send = gr.Button("Enviar", variant="primary", scale=1)

    txt_error = gr.Markdown(value="")

    gr.Examples(
        examples=[
            ["¿Qué cubre el seguro a todo riesgo?"],
            ["Se me ha roto una tubería, ¿qué hago?"],
            ["¿Qué seguro necesita una compañía de teatro para una gira?"],
            ["Quiero contratar una póliza, ¿cuánto cuesta?"],
        ],
        inputs=txt_input,
        label="Ejemplos de consultas",
    )

    state_history = gr.State([])

    btn_send.click(
        fn=chat,
        inputs=[txt_input, state_history],
        outputs=[chatbot, txt_input, txt_error],
    )
    txt_input.submit(
        fn=chat,
        inputs=[txt_input, state_history],
        outputs=[chatbot, txt_input, txt_error],
    )

    chatbot.change(fn=lambda h: h, inputs=[chatbot], outputs=[state_history])

if __name__ == "__main__":
    demo.launch(server_port=7860, share=False)