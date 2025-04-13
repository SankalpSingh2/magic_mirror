document.getElementById('upload-form').addEventListener('submit', function(e) {
e.preventDefault();  // Prevent default form submission

const form = e.target;
const fileInput = form.querySelector('input[name="file"]');
const file = fileInput.files[0];

if (!file) {
    alert("Please select a file!");
    return;
}

const formData = new FormData();
formData.append('file', file);

const xhr = new XMLHttpRequest();
xhr.open('POST', '/upload');

// Update the progress bar during upload
xhr.upload.onprogress = function(event) {
    if (event.lengthComputable) {
    const percentComplete = Math.round((event.loaded / event.total) * 100);
    document.getElementById('upload-progress').value = percentComplete;
    }
};

xhr.onload = function() {
    if (xhr.status === 200) {
    alert("Upload successful!");
    } else {
    alert("Upload failed: " + xhr.responseText);
    }
};

xhr.onerror = function() {
    alert("Upload error");
};

xhr.send(formData);
});