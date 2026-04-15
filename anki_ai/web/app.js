(function () {
  "use strict";

  function send(type, payload) {
    if (typeof pycmd !== "function") {
      return Promise.reject(new Error("Anki bridge is not available."));
    }

    return new Promise(function (resolve) {
      pycmd(
        JSON.stringify({
          type: type,
          payload: payload || {},
        }),
        resolve
      );
    });
  }

  window.AnkiAI = {
    send: send,
    receive: function (message) {
      window.AnkiAI.lastMessage = message;
    },
    lastMessage: null,
  };

  function App() {
    return null;
  }

  function mount() {
    var rootElement = document.getElementById("anki-ai-root");
    if (!rootElement || !window.React || !window.ReactDOM) {
      return;
    }

    var root = window.ReactDOM.createRoot(rootElement);
    root.render(window.React.createElement(App));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
