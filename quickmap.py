import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import nmap
import threading
import subprocess
import os

# --- PARCHE DE INVISIBILIDAD PARA WINDOWS ---
if os.name == 'nt':
    original_popen = subprocess.Popen
    def popen_invisible(*args, **kwargs):
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        kwargs['startupinfo'] = si
        return original_popen(*args, **kwargs)
    subprocess.Popen = popen_invisible

# --- VARIABLE DE CONTROL ---
terminal_activa = False

# --- Funciones de Lógica ---
def iniciar_hilo():
    if terminal_activa: return
    
    ip = entrada_ip.get().strip()
    if not ip:
        actualizar_estado("[ ERROR: Ingrese IP ]", "#FF0000")
        return
        
    hilo = threading.Thread(target=tarea_escaneo)
    hilo.setDaemon(True) 
    hilo.start()

def tecla_modo(indice):
    combo_tipo.current(indice)
    actualizar_estado(f"MODO: {combo_tipo.get()} seleccionado", "#00FF00")

def actualizar_estado(mensaje, color="#008800"):
    label_ayuda.config(text=mensaje, fg=color)

# --- SISTEMA DE ESCANEO MANUAL ---
def modo_terminal(event=None):
    global terminal_activa
    terminal_activa = True
    
    frame_config.pack_forget()
    frame_botones.pack_forget()
    progreso.pack_forget()
    
    texto_resultado.config(height=35) 
    texto_resultado.delete('1.0', tk.END)
        
    texto_resultado.insert(tk.END, ">>> QUICKMAP TERMINAL v0.3\n>>> Escriba argumentos (ej: -F [IP]) y ENTER.\n>>> F6 para regresar a la interfaz gráfica.\n" + "═"*60 + "\n")
    insertar_prompt()
    
    texto_resultado.focus()
    actualizar_estado("[ MODO TERMINAL ACTIVO ]", "#00FFFF")

def insertar_prompt():
    if texto_resultado.get("1.0", tk.END).strip() != "":
        texto_resultado.insert(tk.END, "\n")
    
    texto_resultado.insert(tk.END, "root@quickmap:~# ")
    texto_resultado.mark_set("fin_prompt", "insert")
    texto_resultado.mark_gravity("fin_prompt", tk.LEFT)
    
    texto_resultado.tag_add("protegido", "1.0", "insert")
    texto_resultado.mark_set("insert", tk.END)
    texto_resultado.see(tk.END)

def modo_gui(event=None):
    global terminal_activa
    terminal_activa = False
    
    texto_resultado.tag_remove("protegido", "1.0", tk.END)
    
    frame_config.pack(padx=20, pady=10, fill="x", before=texto_resultado)
    frame_botones.pack(pady=5, before=texto_resultado)
    
    texto_resultado.config(height=22)
    limpiar_consola()

# --- VALIDACIÓN DE EDICIÓN EN TIEMPO REAL ---
def validar_escritura(event):
    if not terminal_activa: return
    
    # Si el usuario intenta borrar texto protegido, se bloquea la acción
    if event.keysym in ("BackSpace", "Delete"):
        # Si la posición actual tiene el tag "protegido", se bloquea el borrado
        if "protegido" in texto_resultado.tag_names(tk.INSERT) or \
           "protegido" in texto_resultado.tag_names("insert - 1c"):
            return "break"
            
    # Si el usuario intenta escribir en una zona protegida, salta al final
    if "protegido" in texto_resultado.tag_names(tk.INSERT):
        texto_resultado.mark_set("insert", tk.END)

def validar_borrado(event):
    if not terminal_activa: return
    
    if event.keysym == "BackSpace":
        # Si el cursor intenta retroceder más allá de la marca del prompt, se bloquea la acción
        if texto_resultado.compare("insert", "<=", "fin_prompt"):
            return "break"
            
    if "protegido" in texto_resultado.tag_names(tk.INSERT):
        texto_resultado.mark_set("insert", tk.END)

def manejar_enter_terminal(event):
    if not terminal_activa: return 

    comando = texto_resultado.get("fin_prompt", tk.END).strip()
    
    if comando.lower() == "clear":
        limpiar_pantalla_terminal()
        return "break"

    texto_resultado.insert(tk.END, "\n")
    
    if comando:
        if comando.lower().startswith("nmap "):
            comando = comando[5:].strip()

        texto_resultado.insert(tk.END, f"[*] EJECUTANDO: nmap {comando}\n[ TRABAJANDO... ]\n")
        texto_resultado.see(tk.END)
        texto_resultado.tag_add("protegido", "1.0", tk.END)
        threading.Thread(target=lambda: tarea_manual(comando), daemon=True).start()
    else:
        insertar_prompt()
            
    return "break"

def limpiar_pantalla_terminal():
    # 1. Quitamos la protección temporalmente para poder borrar
    texto_resultado.tag_remove("protegido", "1.0", tk.END)
    texto_resultado.delete('1.0', tk.END)
    
    # 2. Reinsertamos el encabezado de indicaciones
    encabezado = ">>> QUICKMAP TERMINAL v0.3\n>>> Escriba argumentos (ej: -F [IP]) y ENTER.\n>>> F6 para regresar a la interfaz gráfica.\n" + "═"*60 + "\n"
    texto_resultado.insert(tk.END, encabezado)
    
    # 3. Ponemos un prompt nuevo y se protege la zona
    insertar_prompt()
    actualizar_estado("[ TERMINAL LIMPIA ]", "#00FFFF")

def tarea_manual(comando_bruto):
    partes = comando_bruto.split()
    if not partes: return

    target = ""
    indice_target = -1
    
    # Lista de banderas de Nmap que "secuestran" el siguiente valor
    flags_con_parametro = ["-p", "--top-ports", "--max-retries", "--scan-delay", "-e", "--min-rate", "--max-rate", "-iL"]
    
    for i, p in enumerate(partes):
        if not p.startswith("-"):
            # Si el elemento anterior era -p (u otra flag de la lista), esto es un parámetro, no la IP
            if i > 0 and partes[i-1] in flags_con_parametro:
                continue
                
            # Si pasamos el filtro, lo guardamos como target. 
            # (Sin el 'break', así siempre se queda con el último válido, que es el estándar de Nmap)
            target = p
            indice_target = i

    if not target:
        target = partes[-1]
        indice_target = len(partes) - 1

    argumentos = [p for i, p in enumerate(partes) if i != indice_target]
    args_str = " ".join(argumentos)

    if not target or target.startswith("-"):
        ventana.after(0, lambda: (
            texto_resultado.insert(tk.END, "\n[!] ERROR: No se detectó un objetivo válido.\n", "error"),
            insertar_prompt()
        ))
        return
        

    try:
        # Lógica de búsqueda de motor Nmap
        try:
            nm_manual = nmap.PortScanner()
        except:
            ruta_nmap = [r"C:\Program Files (x86)\Nmap\nmap.exe"]
            nm_manual = nmap.PortScanner(nmap_search_path=ruta_nmap)
            
        nm_manual.scan(hosts=target, arguments=args_str)
        
        if nm_manual.all_hosts():
            ventana.after(0, lambda: imprimir_en_terminal(nm_manual))
        else:
            ventana.after(0, lambda: (
                texto_resultado.insert(tk.END, f"\n[!] Sin respuesta de {target} (Host Down).\n", "error"), 
                insertar_prompt()
            ))
    except Exception as e:
        ventana.after(0, lambda: (
            texto_resultado.insert(tk.END, f"\n[!] CLI_ERROR: {e}\n", "error"), 
            insertar_prompt()
        ))
    
    ventana.after(0, lambda: texto_resultado.see(tk.END))

def imprimir_en_terminal(nm_resultado):
    for host in nm_resultado.all_hosts():
        hostname = nm_resultado[host].hostname()
        nombre = f"{hostname} ({host})" if hostname else host
        res_header = f"\n» REPORT FOR: {nombre} ({nm_resultado[host].state().upper()})\n"
        texto_resultado.insert(tk.END, res_header)
        
        # --- DETECCIÓN DE SISTEMA OPERATIVO ---
        if 'osmatch' in nm_resultado[host] and nm_resultado[host]['osmatch']:
            os_name = nm_resultado[host]['osmatch'][0]['name']
            accuracy = nm_resultado[host]['osmatch'][0]['accuracy']
            texto_resultado.insert(tk.END, f"   OS: {os_name} ({accuracy}% precisión)\n")

        # --- DETECCIÓN DE SERVICIOS Y VERSIONES ---
        if nm_resultado[host].all_protocols():
            header = f"   {'PORT':<10} {'STATE':<10} {'SERVICE':<15} {'VERSION':<20}\n"
            texto_resultado.insert(tk.END, header)
            
            for proto in nm_resultado[host].all_protocols():
                for port in sorted(nm_resultado[host][proto].keys()):
                    p_data = nm_resultado[host][proto][port]
                    state = p_data['state']
                    service = p_data['name']
                    
                    # Extraemos versión, producto y extra info si existen (-sV)
                    version = p_data.get('version', '')
                    product = p_data.get('product', '')
                    extrainfo = p_data.get('extrainfo', '')
                    full_version = f"{product} {version} {extrainfo}".strip()
                    
                    # Formateamos la línea
                    linea = f"   {port}/{proto:<5} {state:<10} {service:<15} {full_version:<20}\n"
                    
                    if state == "open":
                        texto_resultado.insert(tk.END, linea, "open")
                    else:
                        texto_resultado.insert(tk.END, linea)
        
        texto_resultado.insert(tk.END, "░"*70 + "\n")
    
    insertar_prompt()
    texto_resultado.see(tk.END)
    

# --- Tareas de Escaneo Estándar ---
def tarea_escaneo():
    ip = entrada_ip.get()
    puertos = entrada_puertos.get().strip()
    tipo = combo_tipo.get()

    progreso.pack(pady=10, after=frame_config) 
    boton_scan.config(state="disabled", text="[ Escaneando... ]")
    actualizar_estado(f"[ TRABAJANDO: Escaneando {ip}... ]", "#FFA500")
    progreso.start(10)

    if ip == "06112023":
        texto_resultado.delete('1.0', tk.END)
        mensaje_especial = """
        ╔══════════════════════════════════════════════╗
        ║            > ACCESO RESTRINGIDO <            ║
        ╠══════════════════════════════════════════════╣
        ║                                              ║
        ║   [ MENSAJE DEL SISTEMA ]:                   ║
        ║   Para la niña de mis ojos...                ║
        ║                                              ║
        ║   "El motivo de mi existencia,               ║
        ║    mi más grande amor.                       ║
        ║    Vivo por tí, hija mía."                   ║
        ║                                              ║
        ║   Te ama mucho, tu padre~                    ║
        ╚══════════════════════════════════════════════╝
        """
        texto_resultado.insert(tk.END, mensaje_especial)
        finalizar_interfaz("EMILY <3")
        return

    if ip.lower() == "about":
        texto_resultado.delete('1.0', tk.END)
        easter_egg = """
        ╔══════════════════════════════════════════════╗
        ║         > Información del Sistema <          ║
        ╠══════════════════════════════════════════════╣
        ║  PROYECTO: QuickMap                          ║
        ║                                              ║
        ║  DESARROLLADOR: [R. Echegaray]               ║
        ║                                              ║
        ║  I love chicken nuggies, con toda mi soul.   ║
        ╚══════════════════════════════════════════════╝
        """
        texto_resultado.insert(tk.END, easter_egg)
        finalizar_interfaz("SYSTEM INFO")
        return
    
    try:
        # Lógica de búsqueda de motor Nmap
        try:
            nm = nmap.PortScanner()
        except:
            ruta_nmap = [r"C:\Program Files (x86)\Nmap\nmap.exe"]
            nm = nmap.PortScanner(nmap_search_path=ruta_nmap)

        argumentos = "" 
        if tipo == "Escaneo Rápido": argumentos += "-Pn -F"
        elif tipo == "Escaneo Intenso": argumentos += "-Pn -T4 -A -O -v"
        elif tipo == "Ping Sweep": argumentos += "-sn"
        
        if puertos == "":
            nm.scan(hosts=ip, arguments=argumentos)
        else:
            nm.scan(hosts=ip, ports=puertos, arguments=argumentos)
            
        ventana.after(0, mostrar_resultados, nm)
        actualizar_estado("[ LISTO: Datos recibidos correctamente ]", "#00FF00")
        
    except Exception as e:
        ventana.after(0, lambda: texto_resultado.insert(tk.END, f"\n[!] SYSTEM_ERROR: {e}\n", "error"))
        actualizar_estado("[ ERROR: Fallo en el motor ]", "#FF0000")
    
    finalizar_interfaz()

def finalizar_interfaz(msg_boton="Iniciar Escaneo"):
    progreso.stop()
    progreso.pack_forget() 
    boton_scan.config(state="normal", text=msg_boton)

def mostrar_resultados(nm):
    texto_resultado.delete('1.0', tk.END)
    stats = nm.scanstats()
    tiempos = stats.get('elapsed', '0')
    
    if not nm.all_hosts():
        texto_resultado.insert(tk.END, ">>> [!] No se detectaron hosts o dirección inválida.\n")
        actualizar_estado("[ ADVERTENCIA: No se hallaron objetivos ]", "#FFFF00")
        return

    texto_resultado.insert(tk.END, f"╔══════════════════════════════════════════════════════════╗\n")
    texto_resultado.insert(tk.END, f"║    Escaneo completado en {tiempos}s - Datos Recibidos.    ║\n")
    texto_resultado.insert(tk.END, f"╚══════════════════════════════════════════════════════════╝\n\n")

    for host in nm.all_hosts():
        hostname = nm[host].hostname()
        nombre_mostrar = f"{hostname} ({host})" if hostname else f"{host}"
        texto_resultado.insert(tk.END, f"» REPORT FOR: {nombre_mostrar}\n")
        texto_resultado.insert(tk.END, f"   Status: {nm[host].state().upper()}\n")
        
        if 'osmatch' in nm[host] and nm[host]['osmatch']:
            os_name = nm[host]['osmatch'][0]['name']
            accuracy = nm[host]['osmatch'][0]['accuracy']
            texto_resultado.insert(tk.END, f"   OS: {os_name} (Precisión: {accuracy}%)\n")
        
        if 'vendor' in nm[host] and nm[host]['vendor']:
            for mac, vendor in nm[host]['vendor'].items():
                texto_resultado.insert(tk.END, f"   MAC: {mac} [{vendor}]\n")
        
        if nm[host].all_protocols():
            texto_resultado.insert(tk.END, f"\n   {'PORT':<12} {'STATE':<12} {'SERVICE':<15}\n")
            texto_resultado.insert(tk.END, f"   " + "-"*35 + "\n")
            for proto in nm[host].all_protocols():
                for port in sorted(nm[host][proto].keys()):
                    state = nm[host][proto][port]['state']
                    service = nm[host][proto][port]['name']
                    p_proto = f"{port}/{proto}"
                    texto_resultado.insert(tk.END, f"   {p_proto:<12} {state:<12} {service:<15}\n")
        elif combo_tipo.get() != "Ping Sweep":
            texto_resultado.insert(tk.END, "   [i] Sin puertos abiertos.\n")
        else:
            texto_resultado.insert(tk.END, "   [i] Host activo detectado.\n")
            
        texto_resultado.insert(tk.END, "\n" + "░"*60 + "\n")

def limpiar_consola():
    texto_resultado.delete('1.0', tk.END)
    texto_resultado.insert(tk.END, ">>> Limpieza completada... En espera.\n")
    entrada_ip.delete(0, tk.END)
    entrada_ip.insert(0, "")
    entrada_puertos.delete(0, tk.END)
    progreso.pack_forget()
    actualizar_estado("[F1-F3]: Modos | [F5]: Terminal | [ENT]: Scan | [DEL]: Wipe | [F12]: Save")

def guardar_log():
    contenido = texto_resultado.get("1.0", tk.END)
    if len(contenido.strip()) <= 35:
        messagebox.showwarning("Aviso", "No hay datos de escaneo para guardar.")
        return

    archivo = filedialog.asksaveasfilename(
        defaultextension=".txt",
        filetypes=[("Archivos de texto", "*.txt"), ("Todos los archivos", "*.*")],
        title="Guardar Log de Escaneo"
    )
    
    if archivo:
        try:
            with open(archivo, "w", encoding="utf-8") as f:
                f.write(contenido)
            messagebox.showinfo("Éxito", "Reporte guardado correctamente.")
            actualizar_estado("[ LOG GUARDADO CON ÉXITO ]", "#00FFFF")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar: {e}")

# --- CONTROL MAESTRO DE ENTRADA ---
def control_enter_general(event):
    if terminal_activa:
        # Si la terminal está activa, ejecutamos su lógica
        manejar_enter_terminal(event)
        return "break" # Bloqueo total
    else:
        # Si estamos en la GUI, ejecutamos el escaneo normal
        iniciar_hilo()
        return "break" # Bloqueo total
    
# --- Interfaz Visual ---
ventana = tk.Tk()
ventana.title("QuickMap")
ventana.geometry("732x592") 
ventana.configure(bg="#050505")

try: ventana.iconbitmap("logo.ico")
except: pass

estilo = ttk.Style()
estilo.theme_use('default')
estilo.configure("TProgressbar", thickness=8, troughcolor='#050505', background='#00FF00', bordercolor="#050505")

fuente_matrix = ("Consolas", 10, "bold")
color_matrix = "#00FF00"


# Frame GUI
frame_config = tk.LabelFrame(ventana, text=" Bienvenido a QuickMap ", bg="#050505", fg=color_matrix, font=fuente_matrix, padx=10, pady=10)
frame_config.pack(padx=20, pady=10, fill="x")

tk.Label(frame_config, text="Dirección IP o Red (ej: 192.168.1.x/24):", bg="#050505", fg=color_matrix, font=fuente_matrix).grid(row=0, column=0, sticky="w", pady=2)
entrada_ip = tk.Entry(frame_config, width=35, bg="#000000", fg=color_matrix, insertbackground=color_matrix, font=fuente_matrix, borderwidth=1, relief="flat")
entrada_ip.grid(row=0, column=1, pady=5, padx=5)
entrada_ip.insert(0, "")

tk.Label(frame_config, text="Rango de Puertos (Opcional):", bg="#050505", fg=color_matrix, font=fuente_matrix).grid(row=1, column=0, sticky="w", pady=2)
entrada_puertos = tk.Entry(frame_config, width=35, bg="#000000", fg=color_matrix, insertbackground=color_matrix, font=fuente_matrix, borderwidth=1, relief="flat")
entrada_puertos.grid(row=1, column=1, pady=5, padx=5)

tk.Label(frame_config, text="Tipo de Escaneo:", bg="#050505", fg=color_matrix, font=fuente_matrix).grid(row=2, column=0, sticky="w", pady=2)
combo_tipo = ttk.Combobox(frame_config, values=["Escaneo Rápido", "Escaneo Intenso", "Ping Sweep"], state="readonly", width=33)
combo_tipo.current(0)
combo_tipo.grid(row=2, column=1, pady=5, padx=5)

progreso = ttk.Progressbar(ventana, orient="horizontal", length=540, mode="indeterminate", style="TProgressbar")

frame_botones = tk.Frame(ventana, bg="#050505")
frame_botones.pack(pady=5)

boton_scan = tk.Button(frame_botones, text="Iniciar Escaneo", command=iniciar_hilo, 
                       bg="#002200", fg=color_matrix, font=fuente_matrix, 
                       activebackground=color_matrix, activeforeground="black", 
                       cursor="hand2", width=18, relief="flat", borderwidth=1)
boton_scan.pack(side="left", padx=5)

boton_guardar = tk.Button(frame_botones, text="Guardar Log", command=guardar_log, 
                          bg="#002222", fg="#00FFFF", font=fuente_matrix, 
                          activebackground="#00FFFF", activeforeground="black", 
                          width=12, relief="flat", cursor="hand2")
boton_guardar.pack(side="left", padx=5)

boton_limpiar = tk.Button(frame_botones, text="Limpiar", command=limpiar_consola, 
                          bg="#1a0000", fg="#ff3333", font=fuente_matrix, 
                          activebackground="#ff3333", activeforeground="black", 
                          width=10, relief="flat", cursor="hand2")
boton_limpiar.pack(side="left", padx=5)

# ÁREA DE TEXTO ÚNICA (GUI Y TERMINAL)
texto_resultado = tk.Text(ventana, height=22, width=75, bg="black", fg=color_matrix, 
                          font=("Consolas", 9), borderwidth=1, relief="solid", padx=10, pady=10,
                          insertbackground=color_matrix)
texto_resultado.pack(padx=20, pady=15)

texto_resultado.tag_configure("error", foreground="#FF3333", font=("Consolas", 9, "bold"))
texto_resultado.tag_configure("open", foreground="#00FF00", font=("Consolas", 9, "bold"))

# BARRA DE ESTADO
label_ayuda = tk.Label(ventana, text="[F1-F3]: Modos | [F5] [F6]: Entrar - Salir de Terminal | [ENT]: Escanear | [DEL]: Limpiar | [F12]: Guardar Log", 
                       bg="#050505", fg="#008800", font=("Consolas", 8))
label_ayuda.pack(side="bottom", pady=5)

# --- BINDEOS ---

ventana.bind('<Delete>', lambda event: limpiar_consola())
ventana.bind('<F12>', lambda event: guardar_log())
ventana.bind('<F1>', lambda event: tecla_modo(0))
ventana.bind('<F2>', lambda event: tecla_modo(1))
ventana.bind('<F3>', lambda event: tecla_modo(2))
ventana.bind('<F5>', modo_terminal)
ventana.bind('<F6>', modo_gui)

texto_resultado.bind('<Key>', validar_borrado)
ventana.bind('<Return>', control_enter_general)
texto_resultado.bind('<Return>', control_enter_general)

entrada_ip.focus_set()


ventana.mainloop()