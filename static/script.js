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

function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type ? 'toast-' + type : ''}`;
    
    toast.innerHTML = `
        <div class="toast-content">${message}</div>
        <button class="toast-close" onclick="this.parentElement.remove()">×</button>
    `;
    
    toastContainer.appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, 5000);
}

function resetButton(button, downloadLink, formType) {
    button.style.display = 'inline-flex';
    button.className = 'btn-convert';
    button.innerHTML = `<i class="fas fa-sync-alt"></i> Convert ${formType}`;
    button.disabled = false;
    button.type = 'submit';
    downloadLink.style.display = 'none';
    downloadLink.href = '#';
}

function checkStatus(downloadId, button, downloadLink, formType) {
    fetch(`/status/${downloadId}`)
        .then(response => response.json())
        .then(data => {
            button.className = 'btn-status';
            button.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${data.status}...`;
            button.disabled = true;
            
            if (data.status === 'Completed' && data.file_path) {
                button.style.display = 'none';
                downloadLink.style.display = 'inline-flex';
                downloadLink.href = `/download/${downloadId}`;
                downloadLink.onclick = (e) => {
                    e.preventDefault();
                    window.location.href = downloadLink.href;
                    resetButton(button, downloadLink, formType);
                };
                showToast('Your download is ready!', 'success');
            } else if (data.status.includes('Error')) {
                button.className = 'status-error';
                button.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${data.status}`;
                button.disabled = true;
                showToast(data.status, 'error');
                setTimeout(() => resetButton(button, downloadLink, formType), 5000);
            } else {
                setTimeout(() => checkStatus(downloadId, button, downloadLink, formType), 2000);
            }
        })
        .catch(() => {
            button.className = 'status-error';
            button.innerHTML = `<i class="fas fa-exclamation-circle"></i> Error checking status`;
            button.disabled = true;
            showToast('Error checking download status', 'error');
            setTimeout(() => resetButton(button, downloadLink, formType), 5000);
        });
}

document.addEventListener("DOMContentLoaded", function() {
    updateBitrate();
    document.getElementsByClassName("tablinks")[0].click();

    document.getElementById('audio-form').addEventListener('submit', function(e) {
        e.preventDefault();
        const formData = new FormData(this);
        const button = this.querySelector('.btn-convert');
        const downloadLink = this.querySelector('.btn-download');
        
        button.className = 'btn-status';
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Submitting...';
        button.disabled = true;
        downloadLink.style.display = 'none';


        fetch('/download_audio', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                button.className = 'status-error';
                button.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${data.error}`;
                button.disabled = true;
                showToast(data.error, 'error');
                setTimeout(() => resetButton(button, downloadLink, 'Audio'), 5000);
            } else {
                checkStatus(data.download_id, button, downloadLink, 'Audio');
            }
        })
        .catch(() => {
            button.className = 'status-error';
            button.innerHTML = '<i class="fas fa-exclamation-circle"></i> Error submitting request';
            button.disabled = true;
            showToast('Error submitting request', 'error');
            setTimeout(() => resetButton(button, downloadLink, 'Audio'), 5000);

        });
    });

    document.getElementById('video-form').addEventListener('submit', function(e) {
        e.preventDefault();
        const formData = new FormData(this);
        const button = this.querySelector('.btn-convert');
        const downloadLink = this.querySelector('.btn-download');
        
        button.className = 'btn-status';
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Submitting...';
        button.disabled = true;
        downloadLink.style.display = 'none';

        fetch('/download_video', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                button.className = 'status-error';
                button.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${data.error}`;
                button.disabled = true;
                showToast(data.error, 'error');
                setTimeout(() => resetButton(button, downloadLink, 'Video'), 5000);
            } else {
                checkStatus(data.download_id, button, downloadLink, 'Video');
            }
        })
        .catch(() => {
            button.className = 'status-error';
            button.innerHTML = '<i class="fas fa-exclamation-circle"></i> Error submitting request';
            button.disabled = true;
            showToast('Error submitting request', 'error');
            setTimeout(() => resetButton(button, downloadLink, 'Video'), 5000);
        });
    });
});