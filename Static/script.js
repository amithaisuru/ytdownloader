//swith tabs
function openTab(evt, tabName) {
    var i, tabContent, tabLinks;
    tabContent = document.getElementsByClassName("tabcontent");
    for(i=0; i<tabContent.length; i++){
        tabContent[i].style.display = "none";
    }
    tabLinks = document.getElementsByClassName("tablinks");
    for(i=0; i<tabLinks.length; i++){
        tabLinks[i].className = tabLinks[i].className.replace(" active", "");
    }
    document.getElementById(tabName).style.display = "block";
    evt.currentTarget.className += " active";
}

//update bitrate of audio beased on selected audio format
function updateBitrate() {
    const format = document.getElementById('format_audio').value;
    const bitrate = document.getElementById('bitrate');

    bitrate.innerHTML = ''; //clear exsisiting options
    const options = {
        'mp3': [64, 128, 192, 256, 320],
        'm4a': [128],
        // 'aac': [96, 128, 192],
        // 'ogg': [64, 128, 192, 256]
    };

    options[format].forEach(b => {
        let option = document.createElement('option');
        option.value = b
        option.text = `${b} kbps`;
        bitrate.appendChild(option);
    });
}

document.addEventListener("DOMContentLoaded", function(){
    updateBitrate();
    document.getElementsByClassName("tablinks")[0].click();
});