import http.server
import socketserver
import urllib.request
import json
import webbrowser
import threading
import time

PORT = 8080
OLLAMA_URL = "http://localhost:11434/api/generate"

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Claude-like Interface (Ollama)</title>
    <style>
        :root {
            --bg-color: #f8f7f5;
            --chat-bg: #ffffff;
            --text-main: #2d2d2d;
            --text-muted: #737373;
            --accent: #d97757;
            --user-bubble: #e8e6e1;
            --border: #e2e1dc;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 0;
            padding: 0;
            background-color: var(--bg-color);
            color: var(--text-main);
            display: flex;
            height: 100vh;
            flex-direction: column;
        }
        header {
            padding: 1rem 2rem;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            background: var(--chat-bg);
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        h1 { margin: 0; font-size: 1.2rem; font-weight: 500; }
        .tag { background: var(--accent); color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8rem; margin-left: 10px; }
        #chat-container {
            flex-grow: 1;
            overflow-y: auto;
            padding: 2rem;
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
            max-width: 800px;
            margin: 0 auto;
            width: 100%;
            box-sizing: border-box;
        }
        .message {
            display: flex;
            flex-direction: column;
            max-width: 100%;
        }
        .user-message { align-items: flex-end; }
        .user-content {
            background: var(--user-bubble);
            padding: 1rem 1.2rem;
            border-radius: 16px 16px 4px 16px;
            max-width: 85%;
            font-size: 1rem;
            line-height: 1.5;
        }
        .ai-message { align-items: flex-start; }
        .ai-content {
            padding: 0.5rem 1rem;
            max-width: 100%;
            font-size: 1rem;
            line-height: 1.6;
        }
        pre { background: #1e1e1e; color: #d4d4d4; padding: 1rem; border-radius: 8px; overflow-x: auto; }
        code { font-family: 'Courier New', Courier, monospace; }
        .input-area {
            background: var(--chat-bg);
            padding: 1.5rem 2rem;
            border-top: 1px solid var(--border);
            display: flex;
            justify-content: center;
        }
        .input-wrapper {
            max-width: 800px;
            width: 100%;
            position: relative;
            display: flex;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            border-radius: 12px;
            border: 1px solid var(--border);
            background: white;
            padding: 0.5rem;
        }
        textarea {
            width: 100%;
            border: none;
            outline: none;
            resize: none;
            padding: 0.8rem 1rem;
            font-size: 1rem;
            font-family: inherit;
            max-height: 200px;
            overflow-y: auto;
        }
        button {
            background: var(--accent);
            color: white;
            border: none;
            border-radius: 8px;
            padding: 0 1.5rem;
            font-weight: 500;
            cursor: pointer;
            transition: opacity 0.2s;
            margin-left: 0.5rem;
        }
        button:hover { opacity: 0.9; }
        button:disabled { background: var(--text-muted); cursor: not-allowed; }
        .loading { font-style: italic; color: var(--text-muted); }
    </style>
</head>
<body>
    <header>
        <h1>Local AI</h1>
        <span class="tag">Ollama Qwen2.5</span>
    </header>
    
    <div id="chat-container">
        <div class="message ai-message">
            <div class="ai-content">Hello! I am your local AI. How can I help you today?</div>
        </div>
    </div>
    
    <div class="input-area">
        <div class="input-wrapper">
            <textarea id="prompt-input" rows="1" placeholder="Reply to AI... (Shift+Enter for newline)"></textarea>
            <button id="send-btn">Send</button>
        </div>
    </div>

    <script>
        const input = document.getElementById('prompt-input');
        const sendBtn = document.getElementById('send-btn');
        const chatContainer = document.getElementById('chat-container');
        
        // Auto-resize textarea
        input.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 200) + 'px';
        });

        input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        sendBtn.addEventListener('click', sendMessage);

        async function sendMessage() {
            const text = input.value.trim();
            if (!text) return;

            // Add user message
            appendMessage('user', text);
            input.value = '';
            input.style.height = 'auto';
            
            // Disable input while generating
            input.disabled = true;
            sendBtn.disabled = true;

            const aiBubble = appendMessage('ai', '<span class="loading">Thinking...</span>', true);

            try {
                // Send request back to our python proxy
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    body: JSON.stringify({ prompt: text, model: 'qwen2.5:14b' })
                });
                
                if (!response.ok) throw new Error('Failed to connect');

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                aiBubble.innerHTML = ''; // clear loading
                
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    const chunk = decoder.decode(value, { stream: true });
                    // Parse line-delimited JSON
                    const lines = chunk.split('\\n').filter(l => l.trim() !== '');
                    for (let line of lines) {
                        try {
                            const data = JSON.parse(line);
                            if (data.response) {
                                // Simple text replacement for newlines, real impl would use markdown parser
                                aiBubble.innerHTML += data.response.replace(/\\n/g, '<br>');
                                chatContainer.scrollTop = chatContainer.scrollHeight;
                            }
                        } catch (e) {
                            console.error("Parse error chunk", line, e);
                        }
                    }
                }
            } catch (err) {
                aiBubble.innerHTML = `<span style="color:red">Error: Could not connect to Ollama. Make sure you run 'ollama run qwen2.5:14b' first!</span>`;
            }

            input.disabled = false;
            sendBtn.disabled = false;
            input.focus();
        }

        function appendMessage(role, content, isHtml=false) {
            const div = document.createElement('div');
            div.className = `message ${role}-message`;
            const inner = document.createElement('div');
            inner.className = `${role}-content`;
            
            if (isHtml) {
                inner.innerHTML = content;
            } else {
                inner.textContent = content; // sanitize
            }
            
            div.appendChild(inner);
            chatContainer.appendChild(div);
            chatContainer.scrollTop = chatContainer.scrollHeight;
            return inner;
        }
    </script>
</body>
</html>
"""

class ClaudeProxyHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML_CONTENT.encode('utf-8'))
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == '/api/chat':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            # Forward to local ollama instance
            req = urllib.request.Request(OLLAMA_URL, data=post_data, headers={'Content-Type': 'application/json'})
            
            try:
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                
                with urllib.request.urlopen(req) as response:
                    while True:
                        chunk = response.read(1024)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        self.wfile.flush()
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Error connecting to Ollama: {str(e)}".encode('utf-8'))
        else:
            self.send_error(404)

if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), ClaudeProxyHandler) as httpd:
        print(f"Serving UI at http://localhost:{PORT}")
        threading.Thread(target=lambda: webbrowser.open(f"http://localhost:{PORT}")).start()
        httpd.serve_forever()
