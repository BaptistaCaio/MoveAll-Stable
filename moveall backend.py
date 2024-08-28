import os
import sys
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import logging
import gettext
import psutil
import zipfile
import tempfile

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# Set up logging
logging.basicConfig(filename='moveall.log', level=logging.ERROR)

# Set up localization
_ = gettext.gettext
if os.path.exists(resource_path("locales")):
    lang = gettext.translation('moveall', localedir=resource_path('locales'), languages=['pt_BR'])
    lang.install()
    _ = lang.gettext

print(f"Locales path: {resource_path('locales')}")
# Adicione prints similares para outros recursos, se houver

class FileManager:
    def __init__(self):
        self.origem = ""
        self.destino = ""
        self.lista_arquivos = []
        self.dominios_bloqueados = []
        self.janela = None
        self.label_origem = None
        self.label_destino = None
        self.label_status = None
        self.listbox_arquivos = None
        self.label_quantidade = None
        self.progress_bar = None
        self.progress_label = None
        self.extensoes_selecionadas = []
        self.tamanho_lote = 50  # Aumentamos o tamanho padrão do lote
        self.tamanho_limite_pequeno = 1024 * 1024  # 1 MB
        self.cancelar_operacao = False
        self.arquivos_movidos = []
        self.pasta_outros = "outros"
        self.temp_dir = None
        self.is_zip_source = False

    def iniciar_interface(self):
        """Initialize the user interface."""
        self.janela = tk.Tk()
        self.janela.title(_("MoveAll"))
        self.janela.geometry("800x600")

        # Frame principal
        main_frame = tk.Frame(self.janela)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Frame para botões de interação
        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 20))  # Adicionado padding superior e inferior

        # Frame interno para centralizar os botões
        inner_button_frame = tk.Frame(button_frame)
        inner_button_frame.pack(expand=True)

        botao_pasta_origem = tk.Button(inner_button_frame, text=_("Selecionar Pasta"), command=self.selecionar_pasta_origem)
        botao_pasta_origem.pack(side=tk.LEFT, padx=(0, 5))

        botao_zip_origem = tk.Button(inner_button_frame, text=_("Selecionar ZIP"), command=self.selecionar_zip_origem)
        botao_zip_origem.pack(side=tk.LEFT, padx=5)

        botao_destino = tk.Button(inner_button_frame, text=_("Selecionar Destino"), command=self.selecionar_destino)
        botao_destino.pack(side=tk.LEFT, padx=5)

        botao_extensoes = tk.Button(inner_button_frame, text=_("Selecionar Extensões"), command=self.selecionar_extensoes)
        botao_extensoes.pack(side=tk.LEFT, padx=5)

        self.botao_mover = tk.Button(inner_button_frame, text=_("Mover Arquivos"), command=self.iniciar_mover_arquivos)
        self.botao_mover.pack(side=tk.LEFT, padx=5)

        self.botao_cancelar = tk.Button(inner_button_frame, text=_("Cancelar"), command=self.cancelar_mover_arquivos, state=tk.DISABLED)
        self.botao_cancelar.pack(side=tk.LEFT, padx=5)

        # Labels para origem e destino
        self.label_origem = tk.Label(main_frame, text="", anchor="w")
        self.label_origem.pack(fill=tk.X)

        self.label_destino = tk.Label(main_frame, text="", anchor="w")
        self.label_destino.pack(fill=tk.X)

        # Frame para a barra de progresso e label
        progress_frame = tk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=10)

        self.progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", length=300, mode="determinate")
        self.progress_bar.pack(side=tk.LEFT, expand=True, fill=tk.X)

        self.progress_label = tk.Label(progress_frame, text="0 / 0")
        self.progress_label.pack(side=tk.RIGHT, padx=(10, 0))

        self.label_status = tk.Label(main_frame, text="")
        self.label_status.pack(fill=tk.X)

        # Frame para a lista de arquivos
        list_frame = tk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.label_quantidade = tk.Label(list_frame, text=_("Arquivos encontrados: 0"))
        self.label_quantidade.pack(anchor="w")

        # Listbox com scrollbar
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.listbox_arquivos = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
        self.listbox_arquivos.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar.config(command=self.listbox_arquivos.yview)

        # Configurar redimensionamento
        self.janela.columnconfigure(0, weight=1)
        self.janela.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)

        self.janela.mainloop()

    def selecionar_pasta_origem(self):
        """Select the source directory."""
        origem = filedialog.askdirectory(title=_("Selecionar pasta de origem"))
        if origem:
            self.origem = origem
            self.is_zip_source = False
            self.label_origem.config(text=_("Origem: ") + self.origem)
            self.listar_arquivos()

    def selecionar_zip_origem(self):
        """Select the source ZIP file."""
        origem = filedialog.askopenfilename(title=_("Selecionar arquivo ZIP"), filetypes=[("ZIP files", "*.zip")])
        if origem:
            self.origem = self.extrair_zip(origem)
            self.is_zip_source = True
            self.label_origem.config(text=_("Origem (ZIP): ") + origem)
            self.listar_arquivos()

    def extrair_zip(self, zip_path):
        """Extract ZIP file to a temporary directory."""
        if self.temp_dir:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        
        self.temp_dir = tempfile.mkdtemp(dir=self.destino)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(self.temp_dir)
        
        return self.temp_dir

    def selecionar_destino(self):
        """Select the destination directory."""
        destino = filedialog.askdirectory()
        if destino:
            self.destino = destino
            self.atualizar_interface()

    def atualizar_interface(self):
        """Update the UI with current directory selections."""
        self.label_origem.config(text=_("Origem: ") + self.origem)
        self.label_destino.config(text=_("Destino: ") + self.destino)

    def listar_arquivos(self):
        """List all files in the source directory and its subdirectories, and update the UI."""
        self.lista_arquivos = []
        for root, dirs, files in os.walk(self.origem):
            for file in files:
                caminho_completo = os.path.join(root, file)
                caminho_relativo = os.path.relpath(caminho_completo, self.origem)
                self.lista_arquivos.append(caminho_relativo)

        self.listbox_arquivos.delete(0, tk.END)
        for arquivo in self.lista_arquivos:
            self.listbox_arquivos.insert(tk.END, arquivo)
        self.label_quantidade.config(text=_("Arquivos encontrados: ") + str(len(self.lista_arquivos)))

    def iniciar_mover_arquivos(self):
        """Start the file moving process in a separate thread."""
        if not self.origem or not self.destino:
            messagebox.showerror(_("Erro"), _("Por favor, selecione a origem e o destino."))
            return
        thread = threading.Thread(target=self.mover_arquivos)
        thread.start()

    def selecionar_extensoes(self):
        """Open a dialog to select file extensions."""
        extensoes = self.obter_extensoes()
        dialog = tk.Toplevel(self.janela)
        dialog.title(_("Selecionar Extensões"))
        
        for ext in extensoes:
            var = tk.BooleanVar()
            cb = tk.Checkbutton(dialog, text=ext, variable=var)
            cb.pack(anchor="w")
            ext_dict = {"ext": ext, "var": var}
            self.extensoes_selecionadas.append(ext_dict)
        
        tk.Button(dialog, text=_("OK"), command=dialog.destroy).pack()

    def obter_extensoes(self):
        """Get unique file extensions from all files in the source directory and its subdirectories."""
        extensoes = set()
        for arquivo in self.lista_arquivos:
            _, ext = os.path.splitext(arquivo)
            if ext:
                extensoes.add(ext.lower())
        return sorted(list(extensoes))

    def verificar_tamanho_arquivo(self, caminho_arquivo):
        """Verifica o tamanho do arquivo e retorna True se for leve, False caso contrário."""
        try:
            tamanho = os.path.getsize(caminho_arquivo)
            return tamanho <= self.tamanho_limite_pequeno
        except Exception as e:
            logging.error(f"Erro ao verificar tamanho do arquivo {caminho_arquivo}: {str(e)}")
            return False

    def ajustar_tamanho_lote(self, arquivos):
        """Adjust batch size based on CPU usage and file sizes."""
        uso_cpu = psutil.cpu_percent(interval=1)
        arquivos_pequenos = [arquivo for arquivo in arquivos if os.path.getsize(os.path.join(self.origem, arquivo)) < self.tamanho_limite_pequeno]
        
        if uso_cpu >= 80:
            return 10
        elif arquivos_pequenos:
            return len(arquivos_pequenos)  # Move todos os arquivos pequenos de uma vez
        else:
            return 50  # Tamanho de lote padrão para arquivos maiores

    def mover_arquivo(self, arquivo_relativo, extensoes_ativas):
        """Move a single file to its corresponding extension folder or 'outros' folder."""
        _, ext = os.path.splitext(arquivo_relativo)
        caminho_origem = os.path.join(self.origem, arquivo_relativo)

        if ext.lower() in extensoes_ativas:
            pasta_destino = os.path.join(self.destino, ext.lower()[1:])
        else:
            pasta_destino = os.path.join(self.destino, self.pasta_outros)

        caminho_destino = os.path.join(pasta_destino, os.path.basename(arquivo_relativo))

        try:
            if not os.path.exists(pasta_destino):
                os.makedirs(pasta_destino)

            if not os.access(caminho_origem, os.R_OK) or not os.access(os.path.dirname(caminho_destino), os.W_OK):
                raise PermissionError(f"Permissão negada para mover {arquivo_relativo}")

            shutil.move(caminho_origem, caminho_destino)
            self.arquivos_movidos.append((caminho_origem, caminho_destino))
            return True
        except Exception as e:
            logging.error(f"Erro ao mover {arquivo_relativo}: {str(e)}")
            messagebox.showerror(_("Erro"), _(f"Não foi possível mover {arquivo_relativo}: {str(e)}"))
        return False

    def mover_arquivos(self):
        """Move files from the origin to the destination based on their extensions."""
        self.arquivos_movidos = []
        arquivos_movidos_count = 0
        total_files = len(self.lista_arquivos)

        self.progress_bar["maximum"] = total_files
        self.progress_bar["value"] = 0

        extensoes_ativas = [ext["ext"] for ext in self.extensoes_selecionadas if ext["var"].get()]

        self.botao_mover.config(state=tk.DISABLED)
        self.botao_cancelar.config(state=tk.NORMAL)

        i = 0
        while i < total_files:
            if self.cancelar_operacao:
                break

            # Determina o tamanho do próximo lote
            proximos_arquivos = self.lista_arquivos[i:]
            self.tamanho_lote = self.ajustar_tamanho_lote(proximos_arquivos)

            lote = proximos_arquivos[:self.tamanho_lote]
            for arquivo_relativo in lote:
                if self.cancelar_operacao:
                    break
                if self.mover_arquivo(arquivo_relativo, extensoes_ativas):
                    arquivos_movidos_count += 1

                self.progress_bar["value"] = arquivos_movidos_count
                self.progress_label.config(text=f"{arquivos_movidos_count} / {total_files}")
                self.label_status.config(text=_("Arquivos movidos: ") + str(arquivos_movidos_count))
                self.janela.update()

            i += len(lote)

        if self.cancelar_operacao:
            self.desfazer_movimentacao()
            messagebox.showinfo(_("Cancelado"), _("Operação cancelada. Os arquivos foram devolvidos à origem."))
        else:
            messagebox.showinfo(_("Concluído"), _(f"Arquivos movidos com sucesso: {arquivos_movidos_count} de {total_files}"))

        self.cancelar_operacao = False
        self.botao_mover.config(state=tk.NORMAL)
        self.botao_cancelar.config(state=tk.DISABLED)
        self.listar_arquivos()

        # Limpar diretório temporário se foi criado a partir de um ZIP
        if self.is_zip_source and self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                logging.info(f"Pasta temporária excluída: {self.temp_dir}")
            except Exception as e:
                logging.error(f"Erro ao excluir pasta temporária {self.temp_dir}: {str(e)}")
            finally:
                self.temp_dir = None
                self.is_zip_source = False

    def cancelar_mover_arquivos(self):
        """Cancel the file moving operation."""
        self.cancelar_operacao = True
        self.botao_cancelar.config(state=tk.DISABLED)

    def desfazer_movimentacao(self):
        """Undo the file movement by moving files back to their original locations."""
        for origem, destino in reversed(self.arquivos_movidos):
            try:
                shutil.move(destino, origem)
            except Exception as e:
                logging.error(f"Erro ao desfazer movimentação de {destino} para {origem}: {str(e)}")
                messagebox.showerror(_("Erro"), _(f"Não foi possível desfazer a movimentação de {os.path.basename(destino)}: {str(e)}"))

        # Limpar diretório temporário se foi criado a partir de um ZIP
        if self.is_zip_source and self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                logging.info(f"Pasta temporária excluída: {self.temp_dir}")
            except Exception as e:
                logging.error(f"Erro ao excluir pasta temporária {self.temp_dir}: {str(e)}")
            finally:
                self.temp_dir = None
                self.is_zip_source = False

    def verificar_dominio_bloqueado(self, arquivo):
        """Check if the file belongs to a blocked domain."""
        # Implemente a lógica de verificação de domínios bloqueados aqui
        return False

if __name__ == "__main__":
    file_manager = FileManager()
    file_manager.iniciar_interface()
