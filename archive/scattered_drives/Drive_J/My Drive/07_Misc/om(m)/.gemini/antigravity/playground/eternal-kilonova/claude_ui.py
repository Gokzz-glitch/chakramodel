import gradio as gr
import ollama

def chat_stream(message, history):
    # Retrieve the list of available models
    try:
        models = [m['name'] for m in ollama.list()['models']]
        # Default to a model if qwen2.5:14b isn't available, but we suggest they pull it.
        # Fallback to the first available model if any exists.
        model_name = "qwen2.5:14b" 
        if not models:
            yield "⚠️ No models found! Please open your terminal and run `ollama run qwen2.5:14b` to download one first."
            return
        elif model_name not in models:
            model_name = models[0] # Just use the first one they have
            
        messages = []
        for human, assistant in history:
            messages.append({"role": "user", "content": human})
            messages.append({"role": "assistant", "content": assistant})
        messages.append({"role": "user", "content": message})
        
        stream = ollama.chat(model=model_name, messages=messages, stream=True)
        
        partial_message = ""
        for chunk in stream:
            if 'message' in chunk and 'content' in chunk['message']:
                partial_message += chunk['message']['content']
                yield partial_message
                
    except Exception as e:
        yield f"⚠️ Error communicating with Ollama: {str(e)}\n\nMake sure Ollama is running in the background!"

with gr.Blocks(theme=gr.themes.Soft(), title="Claude-Like Interface") as demo:
    gr.Markdown("# 🤖 Local Claude Interface (Powered by Ollama)")
    gr.Markdown("Enjoy your fast, private, and local LLM experience!")
    
    gr.ChatInterface(
        chat_stream,
        chatbot=gr.Chatbot(height=600),
        textbox=gr.Textbox(placeholder="Type your message here...", container=False, scale=7),
        title="Local Llama Chat",
        retry_btn="Regenerate",
        undo_btn="Undo",
        clear_btn="Clear",
    )

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860, show_api=False)
