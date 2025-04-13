(function() {
  const downloadButton = document.getElementById('download-button');
  const downloadStatus = document.getElementById('download-status');
  let pollingInterval;
  let outputAvailable = false;
  
  // Function to poll /output
  function checkOutput() {
    const xhr = new XMLHttpRequest();
    xhr.open('GET', '/output');
    xhr.responseType = 'text';
    xhr.onload = function() {
      if (xhr.status === 200) {
        const responseText = xhr.responseText.trim();
        if (responseText !== "no output yet") {
          // Output available; stop polling and enable download button
          clearInterval(pollingInterval);
          downloadButton.disabled = false;
          downloadStatus.textContent = "Output available!";
          outputAvailable = true;
  
          // Unhide the GLB preview container
          const previewContainer = document.getElementById('glb-preview-container');
          if (previewContainer) {
            previewContainer.style.display = 'block';
          }
  
          // Dynamically load glbpreview.js if not already loaded
          if (!document.getElementById('glb-preview-script')) {
            const script = document.createElement('script');
            script.type = 'module';
            script.id = 'glb-preview-script';
            script.src = '/js/glbpreview.js';
            document.body.appendChild(script);
          }
        } else {
          downloadStatus.textContent = "Waiting for output...";
          downloadButton.disabled = true;
        }
      } else {
        downloadStatus.textContent = "Error checking output!";
      }
    };
    xhr.onerror = function() {
      downloadStatus.textContent = "Error checking output!";
    };
    xhr.send();
  }
  
  // Start polling every 1 second
  pollingInterval = setInterval(checkOutput, 1000);
  
  // When download is requested, simply send a GET request to /output
  downloadButton.addEventListener('click', function() {
    if (outputAvailable) {
      window.location.href = "/output";
    }
  });
})();
