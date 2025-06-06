
const slider = document.getElementById('image_index');
slider.oninput = changeImage;
slider.focus()

const raceSelect = document.getElementById('race');
document.getElementById('deleteRaceInput').value = raceSelect.options[raceSelect.selectedIndex].value;
var selectedRaceName = raceSelect.options[raceSelect.selectedIndex].text;

function changeImage(e) {
    image.src = image.src.replace(/\d{4}.jpg/, e.target.value.padStart(4, 0) + '.jpg')
}

function raceChanged(race) {
    if (race === 'preview') {
        document.getElementById('image').src = '/video_stream';
        selectedRaceName = undefined;
        document.getElementById('deleteRaceButton').disabled = true;
    } else {
        document.getElementById('deleteRaceButton').disabled = false;
        selectedRaceName = raceSelect.options[raceSelect.selectedIndex].text;
        document.getElementById('deleteRaceInput').value = race;
        var xhr = new XMLHttpRequest();
        xhr.open('GET', '/image_count?race=' + race, true);
        xhr.onreadystatechange = function () {
            if (xhr.status === 200) {
                // Handle successful response
                var count = parseInt(xhr.responseText);
                slider.max = count;
                slider.value = 1;
                slider.focus()
            } else {
                // Handle error or other status codes
                console.error(xhr.status);
            }
        };
        xhr.send();
        var img = document.getElementById('image');
        img.src = '/static/race/' + race + '/image_0001.jpg';
    }
}

function startRace() {
    var img = document.getElementById('image');
    img.src = '/static/ready_for_race.png';
    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/start_race', true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.send(JSON.stringify({ race: 'start' }));
}

function stopRace() {
    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/stop_race', true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.send(JSON.stringify({ race: 'stop' }));
}

const beforeUnloadHandler = (event) => {
    // Recommended
    event.preventDefault();

    // Included for legacy support, e.g. Chrome/Edge < 119
    event.returnValue = true;
};

function removeBeforeUnloadEventListener() {
    window.removeEventListener('beforeunload', beforeUnloadHandler);
}

const LINE_KEY = 'lineCoordinates';
document.addEventListener('DOMContentLoaded', function () {
    const urlParams = new URLSearchParams(window.location.search);
    const training = urlParams.get('training');

    if (training === 'true') {
        setTimeout(startRace, 1000)
    }

    const form = document.getElementById('settings');
    const savedFormData = new FormData(form);
    form.addEventListener('change', function (event) {
        let targetValue;
        let savedValue;
        if (event.target.type === 'checkbox') {
            targetValue = event.target.checked;
            savedValue = savedFormData.get(event.target.name) === true ? true : false;
        } else {
            targetValue = event.target.value;
            savedValue = savedFormData.get(event.target.name);
        }

        if (savedValue !== targetValue) {
            event.target.classList.add('changed');
        } else {
            event.target.classList.remove('changed');
        }
        document.getElementsByClassName('changed')
        if (document.getElementsByClassName('changed').length > 0) {
            form.classList.add('unsaved-changes');
        } else {
            form.classList.remove('unsaved-changes');
        }
    });

    form.addEventListener('submit', function () {
        // Optional: Remove indicators after submission
        form.querySelectorAll('.changed').forEach(input => input.classList.remove('changed'));
        form.classList.remove('unsaved-changes');
    });

    document.addEventListener('keydown', function (e) {
        if (slider.disabled) {
            return;
        }
        if (slider !== document.activeElement) {
            if (e.key === 'ArrowLeft') {
                slider.value--;
                slider.dispatchEvent(new Event('input'));
                e.preventDefault();
            } else if (e.key === 'ArrowRight') {
                slider.value++;
                slider.dispatchEvent(new Event('input'));
                e.preventDefault();
            }
        }
    });

    window.addEventListener('beforeunload', beforeUnloadHandler);

    const canvas = document.getElementById('canvas');
    const ctx = canvas.getContext('2d');
    canvas.addEventListener('click', handleCanvasClick);

    var coordinates = localStorage.getItem(LINE_KEY);
    if (coordinates) {
        const ctx = canvas.getContext('2d');
        const { x1, y1, x2, y2 } = JSON.parse(coordinates);
        drawRectangle(ctx, x1, y1);
        drawRectangle(ctx, x2, y2);
        drawLine(ctx, x1, y1, x2, y2);
    }

    var firstPoint = undefined;

    function handleCanvasClick(event) {
        if(!goalLinePaintingActive) {
            return;
        }
        const canvasRect = canvas.getBoundingClientRect();
        const x = event.clientX - canvasRect.left;
        const y = event.clientY - canvasRect.top;

        if (!firstPoint) {
            clearCanvas()
            drawRectangle(ctx, x, y);
            firstPoint = { x, y };
        } else {
            drawRectangle(ctx, x, y);
            drawLine(ctx, firstPoint.x, firstPoint.y, x, y);
            localStorage.setItem(LINE_KEY, JSON.stringify({ x1: firstPoint.x, y1: firstPoint.y, x2: x, y2: y }));
            firstPoint = undefined;
            goalLinePaintingActive = false;
        }
    }


});

function clearCanvas() {
    const canvas = document.getElementById('canvas');
    const ctx = canvas.getContext('2d');

    ctx.clearRect(0, 0, canvas.width, canvas.height);
}

function drawRectangle(ctx, x, y) {
    ctx.fillRect(x - 5, y - 5, 10, 10);
}

function drawLine(ctx, x1, y1, x2, y2) {
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
}
