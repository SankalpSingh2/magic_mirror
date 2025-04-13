(function() {
    // Mapping: WASD keys mapped to command names and button IDs.
    const keyMapping = {
      'w': { command: 'forward', buttonId: 'btn-forward' },
      'a': { command: 'left',    buttonId: 'btn-left' },
      's': { command: 'back',    buttonId: 'btn-back' },
      'd': { command: 'right',   buttonId: 'btn-right' }
    };
  
    // Helper function to send a POST request with the given action.
    function sendCommand(command, action) {
      fetch('/' + command, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action })
      }).catch(err => console.error(`Error sending ${command} ${action}:`, err));
    }
  
    // Object to keep track of active keys (so we send only one "pressed" event per key).
    const activeKeys = {};
  
    // Handle keydown events. If a WASD key is pressed and not already active, send "pressed".
    function keyDownHandler(e) {
      const key = e.key.toLowerCase();
      if (key in keyMapping && !activeKeys[key]) {
        activeKeys[key] = true;
        sendCommand(keyMapping[key].command, 'pressed');
        // Add "pressed" class to the corresponding button for visual feedback.
        const btn = document.getElementById(keyMapping[key].buttonId);
        if (btn) btn.classList.add('pressed');
        e.preventDefault();
      }
    }
  
    // Handle keyup events: send "released" for WASD keys and remove visual feedback.
    function keyUpHandler(e) {
      const key = e.key.toLowerCase();
      if (key in keyMapping && activeKeys[key]) {
        delete activeKeys[key];
        sendCommand(keyMapping[key].command, 'released');
        const btn = document.getElementById(keyMapping[key].buttonId);
        if (btn) btn.classList.remove('pressed');
        e.preventDefault();
      }
    }
  
    window.addEventListener('keydown', keyDownHandler);
    window.addEventListener('keyup', keyUpHandler);
  
    // Also attach click and touch event listeners to the directional buttons.
    Object.keys(keyMapping).forEach((key) => {
      const { command, buttonId } = keyMapping[key];
      const btn = document.getElementById(buttonId);
      if (btn) {
        btn.addEventListener('mousedown', () => {
          sendCommand(command, 'pressed');
          btn.classList.add('pressed');
        });
        btn.addEventListener('mouseup', () => {
          sendCommand(command, 'released');
          btn.classList.remove('pressed');
        });
        btn.addEventListener('mouseleave', () => {
          sendCommand(command, 'released');
          btn.classList.remove('pressed');
        });
        btn.addEventListener('touchstart', (e) => {
          e.preventDefault();
          sendCommand(command, 'pressed');
          btn.classList.add('pressed');
        });
        btn.addEventListener('touchend', () => {
          sendCommand(command, 'released');
          btn.classList.remove('pressed');
        });
      }
    });
  })();
  