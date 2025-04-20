// static/script.js
function openTab(evt, tabName) {
    var i, tabContent, tabLinks;
    tabContent = document.getElementsByClassName("tabcontent");
    for (i = 0; i < tabContent.length; i++) {
        tabContent[i].style.display = "none";
    }
    tabLinks = document.getElementsByClassName("tablinks");
    for (i = 0; i < tabLinks.length; i++) {
        tabLinks[i].className = tabLinks[i].className.replace(" active", "");
    }
    document.getElementById(tabName).style.display = "block";
    evt.currentTarget.className += " active";
}

function updateBitrate() {
    const format = document.getElementById('format_audio').value;
    const bitrate = document.getElementById('bitrate');
    bitrate.innerHTML = '';
    const options = {
        'mp3': [64, 128, 192, 256, 320],
        'm4a': [128],
        'aac': [96, 128, 192],
        'ogg': [64, 128, 192, 256]
    };
    options[format].forEach(b => {
        let option = document.createElement('option');
        option.value = b;
        option.text = `${b} kbps`;
        bitrate.appendChild(option);
    });
}

function checkStatus(downloadId, statusElement) {
    fetch(`/status/${downloadId}`)
        .then(response => response.json())
        .then(data => {
            statusElement.innerHTML = `<p style="color: blue;">Download ID: ${downloadId}, Status: ${data.status}</p>`;
            if (data.status === 'Completed' && data.file_path) {
                statusElement.innerHTML = `<p style="color: blue;">Download ID: ${downloadId}, Status: ${data.status}</p>` +
                                         `<a href="/download/${downloadId}" style="color: green;">Download File</a>`;
            } else if (data.status.includes('Error')) {
                statusElement.innerHTML = `<p style="color: red;">Download ID: ${downloadId}, ${data.status}</p>`;
            } else {
                setTimeout(() => checkStatus(downloadId, statusElement), 2000);
            }
        })
        .catch(() => {
            statusElement.innerHTML = '<p style="color: red;">Error checking status</p>';
        });
}

document.addEventListener("DOMContentLoaded", function() {
    updateBitrate();
    document.getElementsByClassName("tablinks")[0].click();

    document.getElementById('audio-form').addEventListener('submit', function(e) {
        e.preventDefault();
        const formData = new FormData(this);
        const statusDiv = document.getElementById('audio-status');
        
        // Create a new status element for this download
        const statusElement = document.createElement('div');
        statusElement.innerHTML = '<p style="color: blue;">Submitting...</p>';
        statusDiv.appendChild(statusElement);

        fetch('/download_audio', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                statusElement.innerHTML = `<p style="color: red;">${data.error}</p>`;
            } else {
                statusElement.innerHTML = `<p style="color: blue;">Download ID: ${data.download_id}, Status: ${data.status}</p>`;
                checkStatus(data.download_id, statusElement);
            }
        })
        .catch(() => {
            statusElement.innerHTML = '<p style="color: red;">Error submitting request</p>';
        });
    });

    document.getElementById('video-form').addEventListener('submit', function(e) {
        e.preventDefault();
        const formData = new FormData(this);
        const statusDiv = document.getElementById('video-status');
        
        // Create a new status element for this download
        const statusElement = document.createElement('div');
        statusElement.innerHTML = '<p style="color: blue;">Submitting...</p>';
        statusDiv.appendChild(statusElement);

        fetch('/download_video', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                statusElement.innerHTML = `<p style="color: red;">${data.error}</p>`;
            } else {
                statusElement.innerHTML = `<p style="color: blue;">Download ID: ${data.download_id}, Status: ${data.status}</p>`;
                checkStatus(data.download_id, statusElement);
            }
        })
        .catch(() => {
            statusElement.innerHTML = '<p style="color: red;">Error submitting request</p>';
        });
    });
});