document.onkeydown = function (event) {
    switch (event.keyCode) {
        case 37:
            event.preventDefault();
            document.getElementById("video").currentTime -= 0.001;
            break;

        case 39:
            event.preventDefault();
            document.getElementById("video").currentTime += 0.001;
            break;

    }
};