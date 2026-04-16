// ---------- MODAL ----------
function openModal(id) {
  const m = document.getElementById(id);
  if (m) m.classList.add('open');
}
function closeModal(id) {
  const m = document.getElementById(id);
  if (m) m.classList.remove('open');
}
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal.open').forEach((m) => m.classList.remove('open'));
  }
});
document.addEventListener('click', (e) => {
  if (e.target.classList && e.target.classList.contains('modal-backdrop')) {
    e.target.closest('.modal').classList.remove('open');
  }
});

// ---------- Filas de tabla clickeables ----------
document.addEventListener('click', (e) => {
  const row = e.target.closest('.tabla-row-link');
  if (!row) return;
  if (e.target.closest('button, a, form, input')) return;
  const href = row.dataset.href;
  if (href) window.location.href = href;
});

// ---------- Drop zone ----------
function initDropZone(zoneId, inputId, previewId) {
  const zone = document.getElementById(zoneId);
  const input = document.getElementById(inputId);
  const preview = document.getElementById(previewId);
  if (!zone || !input) return;

  zone.addEventListener('click', () => input.click());

  ['dragenter', 'dragover'].forEach((ev) => {
    zone.addEventListener(ev, (e) => {
      e.preventDefault();
      e.stopPropagation();
      zone.classList.add('dragover');
    });
  });
  ['dragleave', 'drop'].forEach((ev) => {
    zone.addEventListener(ev, (e) => {
      e.preventDefault();
      e.stopPropagation();
      zone.classList.remove('dragover');
    });
  });

  zone.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    input.files = files;
    renderPreviews(input, preview);
  });
  input.addEventListener('change', () => renderPreviews(input, preview));
}

function renderPreviews(input, preview) {
  if (!preview) return;
  preview.innerHTML = '';
  Array.from(input.files || []).forEach((file) => {
    if (!file.type.startsWith('image/')) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      const div = document.createElement('div');
      div.className = 'preview-item';
      const img = document.createElement('img');
      img.src = e.target.result;
      div.appendChild(img);
      preview.appendChild(div);
    };
    reader.readAsDataURL(file);
  });
}

// ---------- Form subida: deshabilitar botón ----------
document.addEventListener('submit', (e) => {
  const form = e.target;
  if (form.classList && form.classList.contains('form-upload')) {
    const btn = form.querySelector('button[type="submit"]');
    if (btn) {
      btn.disabled = true;
      btn.dataset.originalText = btn.innerText;
      btn.innerText = 'Subiendo...';
    }
  }
});

// ---------- Flash auto-dismiss ----------
document.addEventListener('DOMContentLoaded', () => {
  const flashes = document.querySelectorAll('.flash');
  flashes.forEach((f) => {
    setTimeout(() => {
      f.classList.add('fade-out');
      setTimeout(() => f.remove(), 400);
    }, 5000);
  });

  // Init drop zones por convención
  initDropZone('dropZoneEvidencias', 'archivosEvidencias', 'previewEvidencias');
});

// Confirmación delete
function confirmDelete(msg) {
  return confirm(msg || '¿Estás seguro de eliminar este elemento?');
}
