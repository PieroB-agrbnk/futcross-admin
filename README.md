---
title: FutCross Admin
emoji: "🟠"
colorFrom: gray
colorTo: orange
sdk: streamlit
app_file: app.py
pinned: false
---

# FUTCROSS · Control de sesiones

Sistema para saber **quién entra a entrenar, cuántas sesiones le quedan y a quién hay que
llamar para que renueve**. Hecho en Python (Streamlit) sobre Supabase. Costo: S/ 0.

---

## Qué resuelve

| Problema | Cómo lo resuelve |
|---|---|
| Nadie controla quién entra | Pantalla **Check-in**: el alumno marca con su DNI en una tablet o celular. Sin recepcionista. |
| El plan de 1 mes trae 12 sesiones | Cada marca descuenta 1 sesión. El marcador muestra `07 / 12` en grande. |
| Se lesionó a mitad del plan | **Congelamientos**: se pausa el paquete y al dar de alta el sistema suma automáticamente los días perdidos al vencimiento. Nadie calcula fechas a mano. |
| No se sabe a quién cobrarle la renovación | **Renovaciones**: lista ordenada por urgencia con botón directo de WhatsApp. |
| Fecha de inscripción | Se guarda por alumno y se muestra en su ficha. |

Reglas duras que aplica el sistema:

- Una sola marca por día por alumno (índice único en base de datos, no solo validación de pantalla).
- Paquete vencido, agotado o congelado → **no descuenta sesión** y queda registrado el intento.
- Anular una asistencia devuelve la sesión al saldo automáticamente (las sesiones usadas se
  cuentan, no se guardan en un contador que se pueda desincronizar).
- Todas las fechas se calculan en hora de Lima, no del servidor. Un entrenamiento de 8 p.m.
  no se registra con la fecha del día siguiente.

---

## Instalación (30 minutos, todo gratis)

### 1. Base de datos en Supabase

1. Crea una cuenta en <https://supabase.com> → **New project** (plan Free).
2. Elige región **South America (São Paulo)**, es la más cercana a Lima.
3. Cuando termine de crearse, entra a **SQL Editor → New query**.
4. Pega el contenido completo de `schema.sql` (esta en la carpeta de arriba) y dale **Run**.
5. Ve a **Settings → API** y copia:
   - `Project URL`
   - la llave **`service_role`** (la secreta, no la `anon`)

### 2. Probar en tu PC (Windows)

```powershell
cd C:\ruta\a\futcross
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
notepad .streamlit\secrets.toml     REM pega tu URL, tu llave y tu PIN
streamlit run app.py
```

Se abre en <http://localhost:8501>. Para ver el sistema con datos ficticios:
`streamlit run seed_demo.py`.

### 3. Publicarlo en internet (Streamlit Community Cloud, gratis)

1. Sube la carpeta a un repositorio de GitHub. **Verifica que `.streamlit/secrets.toml` no
   se haya subido** — ya está en `.gitignore`.
2. Entra a <https://share.streamlit.io> con tu cuenta de GitHub → **New app**.
3. Selecciona el repo, rama `main`, archivo principal `app.py`, y despliega.
4. En **Settings → Secrets** de la app, pega:

```toml
SUPABASE_URL = "https://xxxx.supabase.co"
SUPABASE_KEY = "eyJ...service_role..."
ADMIN_PIN    = "el-pin-que-quieras"
```

Queda una URL tipo `https://futcross.streamlit.app`. Esa es la que abres en la tablet de la cancha.

> **Por qué Streamlit Cloud y no Vercel:** Vercel es excelente pero está pensado para
> JavaScript; correr Python ahí obliga a usar funciones serverless y complica el estado.
> Streamlit Community Cloud es gratis, ilimitado para apps públicas, se despliega desde
> GitHub en un clic y ejecuta Python nativo. Supabase Free da 500 MB de Postgres, de sobra
> para una academia (una sesión pesa menos de 100 bytes).

---

## Cómo se usa el día a día

**En la cancha (tablet o celular fijo):** deja abierta la app sin iniciar sesión de
administrador. Solo se ve la pantalla de Check-in. El alumno escribe su DNI y aparece su
tarjeta con las sesiones que le quedan.

**Recepción / administración:** en la barra lateral, *Entrar como administrador* con el PIN.
Se habilitan:

- **Panel** — cuántos entrenaron hoy, quiénes están por vencer, quién intentó entrar sin paquete.
- **Alumnos** — inscribir, buscar, ver ficha con historial y ritmo semanal.
- **Paquetes** — vender o renovar. Muestra la fecha exacta de vencimiento antes de guardar.
- **Congelamientos** — registrar la lesión y luego dar de alta.
- **Renovaciones** — a quién llamar, con WhatsApp listo.
- **Reportes** — asistencias por día, alumnos más constantes, ingresos por plan, exportar CSV.
- **Planes** — crear o desactivar planes y precios.

### El caso de la lesión, paso a paso

1. Alumno compra el Plan Mensual (12 sesiones, 30 días) el 6 de agosto → vence el 4 de setiembre.
2. Entrena 6 sesiones y se lesiona el 20 de agosto.
3. En **Congelamientos → Congelar**, motivo `LESION`, desde el 20/08. El paquete queda en pausa
   y el kiosco deja de aceptarle marcas (no le come sesiones).
4. Vuelve el 3 de setiembre. En **Congelados**, pones fecha de alta 03/09 y das *Reactivar*.
5. El sistema calcula 15 días de baja y mueve el vencimiento del 04/09 al **19/09**.
   Sus 6 sesiones restantes siguen intactas.

---

## Archivos

```
app.py            todas las pantallas
db.py             consultas a Supabase (nada de SQL suelto en las pantallas)
logic.py          reglas puras: vigencias, congelamientos, alertas
theme.py          identidad visual y el marcador de sesiones
schema.sql        tablas, índices y vistas (se corre una sola vez)
test_logic.py     25 pruebas de las reglas -> python test_logic.py
seed_demo.py      datos de prueba, borrar cuando entren datos reales
```

## Mantenimiento

- **Respaldo:** el plan Free de Supabase **no hace respaldos automáticos**. Exporta los CSV de Alumnos y Paquetes una vez al mes desde el propio panel, o pasa a Pro (25 USD al mes) que sí incluye respaldo diario.
- **La app se duerme:** Streamlit Cloud pausa apps públicas sin tráfico por varios días.
  Vuelve sola al abrir la URL, tarda unos 30 segundos la primera vez.
- **Cambiar precios:** pantalla Planes. Los paquetes ya vendidos conservan el precio con
  el que se cobraron.
- **Sumar sedes:** el campo `sede` ya existe en alumnos y asistencias; solo habría que
  agregar el filtro en Reportes.
