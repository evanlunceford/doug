# pip install pywebview
import webview

HTML = """
<!doctype html>
<html>
  <body>
    <h1>Douglas, the home butler</h1>
    <button onclick="pywebview.api.ping().then(r => alert(r))">Ping Python</button>
  </body>
</html>
"""

class API:
    def ping(self):
        return "Pong from Python!"

if __name__ == "__main__":
    window = webview.create_window("My App", html=HTML, js_api=API())
    webview.start()
