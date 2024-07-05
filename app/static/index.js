function updateImage() {
    var img = document.getElementById('imagePreview');
    img.src = img.src.split('?')[0] + '?' + new Date().getTime();
}