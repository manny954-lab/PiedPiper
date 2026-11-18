/* ============================================================
   PiedPiper Inventario · Interacciones de interfaz
   Sin dependencias externas.
   ============================================================ */
(function () {
  "use strict";

  var doc = document;
  var root = doc.documentElement;

  function $(sel, ctx) { return (ctx || doc).querySelector(sel); }
  function $$(sel, ctx) { return Array.prototype.slice.call((ctx || doc).querySelectorAll(sel)); }

  /* ---------- Tema claro / oscuro ---------- */

  function temaActual() {
    return root.getAttribute("data-theme") === "light" ? "light" : "dark";
  }

  function aplicarTema(tema) {
    root.setAttribute("data-theme", tema);
    try { localStorage.setItem("pp-theme", tema); } catch (e) {}
    $$("[data-theme-toggle]").forEach(function (btn) {
      btn.setAttribute(
        "aria-label",
        tema === "dark" ? "Cambiar a tema claro" : "Cambiar a tema oscuro"
      );
      btn.setAttribute("title", tema === "dark" ? "Tema claro" : "Tema oscuro");
    });
  }

  aplicarTema(temaActual());

  doc.addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-theme-toggle]");
    if (!btn) return;
    aplicarTema(temaActual() === "dark" ? "light" : "dark");
  });

  /* ---------- Barra lateral móvil ---------- */

  function cerrarSidebar() {
    var shell = $(".app-shell");
    if (shell) shell.classList.remove("sidebar-open");
  }

  doc.addEventListener("click", function (ev) {
    if (ev.target.closest("[data-sidebar-open]")) {
      var shell = $(".app-shell");
      if (shell) shell.classList.add("sidebar-open");
      return;
    }
    if (ev.target.closest("[data-sidebar-close]")) {
      cerrarSidebar();
    }
  });

  doc.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape") cerrarSidebar();
  });

  window.addEventListener("resize", function () {
    if (window.innerWidth > 920) cerrarSidebar();
  });

  /* ---------- Mostrar / ocultar contraseña ---------- */

  doc.addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-password-toggle]");
    if (!btn) return;
    var input = doc.getElementById(btn.getAttribute("data-password-toggle"));
    if (!input) return;
    var mostrar = input.type === "password";
    input.type = mostrar ? "text" : "password";
    btn.setAttribute("aria-label", mostrar ? "Ocultar contraseña" : "Mostrar contraseña");
    var on = $("[data-eye-on]", btn);
    var off = $("[data-eye-off]", btn);
    if (on) on.classList.toggle("is-hidden", mostrar);
    if (off) off.classList.toggle("is-hidden", !mostrar);
  });

  /* ---------- Confirmaciones ---------- */

  doc.addEventListener("submit", function (ev) {
    var form = ev.target;
    var btn = ev.submitter;
    var mensaje = (btn && btn.getAttribute("data-confirm")) || form.getAttribute("data-confirm");
    if (mensaje && !window.confirm(mensaje)) {
      ev.preventDefault();
    }
  }, true);

  /* ---------- Avisos flotantes ---------- */

  function cerrarToast(toast) {
    if (!toast || toast.classList.contains("toast--out")) return;
    toast.classList.add("toast--out");
    window.setTimeout(function () { toast.remove(); }, 220);
  }

  $$(".toast").forEach(function (toast) {
    window.setTimeout(function () { cerrarToast(toast); }, 6000);
  });

  doc.addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-toast-close]");
    if (btn) cerrarToast(btn.closest(".toast"));
  });

  /* ---------- Auto-envío de selects ---------- */

  doc.addEventListener("change", function (ev) {
    var campo = ev.target.closest("[data-auto-submit]");
    if (campo && campo.form) campo.form.submit();
  });

  /* ---------- Búsqueda global ---------- */

  var busqueda = $("[data-global-search]");
  if (busqueda) {
    doc.addEventListener("keydown", function (ev) {
      if (ev.key !== "/" || ev.ctrlKey || ev.metaKey || ev.altKey) return;
      var activo = doc.activeElement;
      var etiqueta = activo ? activo.tagName : "";
      if (etiqueta === "INPUT" || etiqueta === "TEXTAREA" || etiqueta === "SELECT") return;
      ev.preventDefault();
      busqueda.focus();
      busqueda.select();
    });
  }

  /* ---------- Credenciales de demostración ---------- */

  doc.addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-demo-email]");
    if (!btn) return;
    var email = doc.getElementById("email");
    var password = doc.getElementById("password");
    if (email) email.value = btn.getAttribute("data-demo-email") || "";
    if (password) password.value = btn.getAttribute("data-demo-password") || "";
    if (email) email.focus();
  });

  /* ---------- Copiar al portapapeles ---------- */

  doc.addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-copy]");
    if (!btn) return;
    var texto = btn.getAttribute("data-copy") || "";
    var original = btn.getAttribute("title") || "Copiar";
    function aviso(ok) {
      btn.setAttribute("title", ok ? "Copiado" : "No se pudo copiar");
      window.setTimeout(function () { btn.setAttribute("title", original); }, 1600);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(texto).then(function () { aviso(true); }, function () { aviso(false); });
    } else {
      var tmp = doc.createElement("textarea");
      tmp.value = texto;
      tmp.setAttribute("readonly", "");
      tmp.style.position = "fixed";
      tmp.style.opacity = "0";
      doc.body.appendChild(tmp);
      tmp.select();
      var ok = false;
      try { ok = doc.execCommand("copy"); } catch (e) {}
      doc.body.removeChild(tmp);
      aviso(ok);
    }
  });

  /* ---------- Vista previa de movimientos ---------- */

  var movForm = $("[data-mov-form]");
  if (movForm) {
    var tipos = $$("[data-mov-tipo]", movForm);
    var selectProducto = $("[data-mov-producto]", movForm);
    var cantidad = $("[data-mov-cantidad]", movForm);
    var motivo = doc.getElementById("motivo");
    var motivoReq = $("[data-motivo-req]", movForm);
    var cantidadLabel = $("[data-cantidad-label]", movForm);
    var cantidadHelp = $("[data-cantidad-help]", movForm);

    var preview = $("[data-stock-preview]");
    var previewVacio = $("[data-preview-empty]", preview || doc);
    var previewBody = $("[data-preview-body]", preview || doc);
    var elProducto = $("[data-preview-producto]", preview || doc);
    var elSku = $("[data-preview-sku]", preview || doc);
    var elActual = $("[data-preview-actual]", preview || doc);
    var elUnidad = $("[data-preview-unidad]", preview || doc);
    var elNuevo = $("[data-preview-nuevo]", preview || doc);
    var elNota = $("[data-preview-nota]", preview || doc);
    var elWarning = $("[data-preview-warning]", preview || doc);

    function tipoSeleccionado() {
      for (var i = 0; i < tipos.length; i++) {
        if (tipos[i].checked) return tipos[i].value;
      }
      return "entrada";
    }

    function opcionProducto() {
      if (!selectProducto || !selectProducto.value) return null;
      return selectProducto.options[selectProducto.selectedIndex] || null;
    }

    function actualizarTipo() {
      var tipo = tipoSeleccionado();
      if (cantidadLabel) {
        cantidadLabel.textContent = tipo === "ajuste" ? "Nuevo stock" : "Cantidad";
      }
      if (cantidadHelp) {
        cantidadHelp.textContent = tipo === "ajuste"
          ? "Escribe el stock real contado."
          : "Unidades que ingresan o salen.";
      }
      if (motivoReq) motivoReq.hidden = tipo !== "ajuste";
      if (motivo) motivo.required = tipo === "ajuste";
    }

    function actualizarPreview() {
      var opcion = opcionProducto();
      var tipo = tipoSeleccionado();
      var valor = parseInt((cantidad && cantidad.value) || "0", 10);
      if (isNaN(valor) || valor < 0) valor = 0;

      if (!opcion || !previewBody) {
        if (previewVacio) previewVacio.classList.remove("is-hidden");
        if (previewBody) previewBody.classList.add("is-hidden");
        return;
      }

      var stock = parseInt(opcion.getAttribute("data-stock") || "0", 10);
      var unidad = opcion.getAttribute("data-unidad") || "pza";
      var sku = opcion.getAttribute("data-sku") || "";
      var nombre = (opcion.textContent || "").split("—")[0].trim();
      var nuevo = stock;

      if (tipo === "entrada") nuevo = stock + valor;
      else if (tipo === "salida") nuevo = stock - valor;
      else nuevo = valor;

      if (previewVacio) previewVacio.classList.add("is-hidden");
      previewBody.classList.remove("is-hidden");
      if (elProducto) elProducto.textContent = nombre || "Producto";
      if (elSku) elSku.textContent = sku;
      if (elActual) elActual.textContent = stock;
      if (elUnidad) elUnidad.textContent = unidad;
      if (elNuevo) elNuevo.textContent = nuevo;

      if (elNota) {
        if (tipo === "entrada") elNota.textContent = "Se suman " + valor + " " + unidad + " al inventario.";
        else if (tipo === "salida") elNota.textContent = "Se retiran " + valor + " " + unidad + " del inventario.";
        else elNota.textContent = "El stock quedará fijado en " + valor + " " + unidad + ".";
      }

      var negativo = tipo === "salida" && nuevo < 0;
      if (elWarning) elWarning.classList.toggle("is-hidden", !negativo);
      if (elNuevo) elNuevo.classList.toggle("text-danger", negativo);
    }

    tipos.forEach(function (radio) {
      radio.addEventListener("change", function () {
        actualizarTipo();
        actualizarPreview();
      });
    });

    if (selectProducto) selectProducto.addEventListener("change", actualizarPreview);
    if (cantidad) {
      cantidad.addEventListener("input", actualizarPreview);
      cantidad.addEventListener("change", actualizarPreview);
    }

    actualizarTipo();
    actualizarPreview();
  }

  /* ---------- Plan de licencia en alta de empresa ---------- */

  var planSelect = $("[data-plan-select]");
  if (planSelect) {
    var maxUsuarios = $("[data-plan-usuarios]");
    var maxProductos = $("[data-plan-productos]");
    var planName = $("[data-plan-name]");
    var planPrice = $("[data-plan-price]");

    function aplicarPlan() {
      var opcion = planSelect.options[planSelect.selectedIndex];
      if (!opcion) return;
      if (maxUsuarios && opcion.getAttribute("data-usuarios")) {
        maxUsuarios.value = opcion.getAttribute("data-usuarios");
      }
      if (maxProductos && opcion.getAttribute("data-productos")) {
        maxProductos.value = opcion.getAttribute("data-productos");
      }
      if (planName) planName.textContent = opcion.getAttribute("data-nombre") || opcion.textContent;
      if (planPrice) planPrice.textContent = opcion.getAttribute("data-precio") || "";
    }

    planSelect.addEventListener("change", aplicarPlan);
  }

  /* ---------- Validación ligera del lado del cliente ---------- */

  $$("form").forEach(function (form) {
    form.addEventListener("submit", function (ev) {
      if (form.hasAttribute("novalidate") && "checkValidity" in form) {
        var invalido = form.querySelector(":invalid");
        if (invalido && form.contains(invalido)) {
          var campo = invalido.closest(".field");
          if (campo) {
            var ayuda = campo.querySelector(".field-help");
            if (ayuda) ayuda.classList.add("text-danger");
            invalido.focus();
          }
        }
      }
    });
  });
})();
