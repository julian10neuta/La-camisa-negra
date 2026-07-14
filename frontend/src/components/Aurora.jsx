// src/components/Aurora.jsx
// ----------------------------------------------------------------------------
// Fondo de la ventana: tres manchas de color desenfocadas que se desplazan
// despacio, como una aurora. Se monta una sola vez en App.jsx, por debajo de
// todas las pantallas.
//
// No tiene lógica: los colores salen de las variables del tema (así sigue a la
// paleta que el usuario haya elegido en Ajustes) y el ajuste de "reducir
// movimiento" lo apaga desde el CSS, sin que este componente se entere. Toda la
// implementación está en index.css, sección "Aurora".
//
// aria-hidden porque es decoración pura: no hay nada que un lector de pantalla
// deba anunciar.
// ----------------------------------------------------------------------------

export default function Aurora() {
  return (
    <div className="aurora" aria-hidden="true">
      <span className="aurora__blob aurora__blob--1" />
      <span className="aurora__blob aurora__blob--2" />
      <span className="aurora__blob aurora__blob--3" />
    </div>
  );
}
