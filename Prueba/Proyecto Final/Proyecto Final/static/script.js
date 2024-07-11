document.addEventListener('DOMContentLoaded', function() {
    var fileInput = document.getElementById('mediaInput');
    var gifForm = document.getElementById('gifForm');
    var videoPreview = document.getElementById('videoPreview');
    var selectedImages = document.getElementById('selectedImages');

    fileInput.addEventListener('change', function(event) {
        var files = event.target.files;
        if (files.length > 0) {
            var file = files[0];
            var fileURL = URL.createObjectURL(file);
            if (file.type.startsWith('image/')) {
                // Mostrar imagen seleccionada
                var img = document.createElement('img');
                img.src = fileURL;
                img.classList.add('selected-image');
                selectedImages.appendChild(img);
                // Ocultar el video
                videoPreview.classList.add('hidden');
            } else if (file.type.startsWith('video/')) {
                // Mostrar video seleccionado
                videoPreview.src = fileURL;
                videoPreview.classList.remove('hidden');
                // Ocultar las imágenes
                selectedImages.innerHTML = '';
            }
        } else {
            // Si no se selecciona ningún archivo, oculta el elemento de videoPreview
            videoPreview.classList.add('hidden');
            selectedImages.innerHTML = '';
        }
    });

    gifForm.addEventListener('submit', function(event) {
        event.preventDefault();
        var files = fileInput.files;
        var duration = document.getElementById('duration').value;
        var start = document.getElementById('start').value;
        var end = document.getElementById('end').value;
        var fpsInput = document.getElementById('fps');
        var fps = fpsInput.value;
        var selectedEffect = document.getElementById('effect').value;
        var percentage = document.getElementById("porcentaje").value;
        var exportFormat = document.getElementById('exportFormat').value;

        var formData = new FormData();
        formData.append('duration', duration);
        formData.append('start', start);
        formData.append('end', end);
        formData.append('fps', fps);
        formData.append('effect', selectedEffect);
        formData.append("percent", percentage); 
        formData.append("exportFormat", exportFormat);

        for (var i = 0; i < files.length; i++) {
            formData.append('fileInput', files[i]);
        }

        fetch('/create_gif', {
            method: 'POST',
            body: formData
        })
        .then(response => response.text())
        .then(result => {
            showAlert(result);
        })
        .catch(error => {
            console.error('Error:', error);
        });
    });

    function showAlert(message) {
        alert(message);
        location.reload();
    }
});

function updateValue(value) {
    document.getElementById('percentage-value').textContent = value + '%';
}

document.getElementById('download').addEventListener('click', function(event) {
    event.preventDefault();  // Prevenir cualquier acción predeterminada

    fetch('/get_files')
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            if (data.files.length > 0) {
                downloadFiles(data.files, 0);
            } else {
                alert('No hay archivos para descargar.');
            }
        } else {
            alert(data.message);
        }
    })
    .catch(error => alert('Error al obtener archivos: ' + error));
});

function downloadFiles(files, index) {
    if (index < files.length) {
        var link = document.createElement('a');
        link.href = `/download_file/${files[index]}`;
        link.download = files[index];
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        // Espera un pequeño intervalo antes de continuar con la siguiente descarga
        setTimeout(() => {
            downloadFiles(files, index + 1);
        }, 1000);
    } else {
        deleteFiles();
    }
}

function deleteFiles() {
    fetch('/delete_files', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        alert(data.message);
        location.reload();
    })
    .catch(error => alert('Error al eliminar archivos: ' + error));
}
