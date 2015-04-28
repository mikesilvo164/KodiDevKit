import sublime_plugin
import sublime
import re
import os
import sys
import codecs
__file__ = os.path.normpath(os.path.abspath(__file__))
__path__ = os.path.dirname(__file__)
libs_path = os.path.join(__path__, 'libs')
if libs_path not in sys.path:
    sys.path.insert(0, libs_path)
from lxml import etree as ET
from polib import polib
from InfoProvider import InfoProvider
from Utils import *
Infos = InfoProvider()
APP_NAME = "kodi"
if sublime.platform() == "linux":
    KODI_PRESET_PATH = "/usr/share/%s/" % APP_NAME
elif sublime.platform() == "windows":
    KODI_PRESET_PATH = "C:/%s/" % APP_NAME
else:
    KODI_PRESET_PATH = ""
SETTINGS_FILE = 'sublimekodi.sublime-settings'
DEFAULT_LANGUAGE_FOLDER = "English"


class SublimeKodi(sublime_plugin.EventListener):

    def __init__(self, **kwargs):
        self.id_list = []
        self.string_list = []
        self.native_string_list = []
        self.builtin_id_list = []
        self.builtin_string_list = []
        self.builtin_native_string_list = []
        self.labels_loaded = False
        self.settings_loaded = False
        self.actual_project = None
        self.prev_selection = None

    def on_window_command(self, window, command_name, args):
        if command_name == "reload_kodi_language_files":
            self.get_settings()
            self.get_builtin_label()
            self.update_labels(window.active_view())
        elif command_name == "search_for_label":
            label_list = ['%s (%s)' % t for t in zip(self.string_list, self.id_list)]
            sublime.active_window().show_quick_panel(label_list, lambda s: self.label_search_ondone_action(s), selected_index=0)

    def label_search_ondone_action(self, index):
        if not index == -1:
            view = sublime.active_window().active_view()
            scope_name = view.scope_name(view.sel()[0].b)
            if "text.xml" in scope_name:
                lang_string = "$LOCALIZE[%s]" % self.id_list[index][1:]
            else:
                lang_string = self.id_list[index][1:]
            view.run_command("insert", {"characters": lang_string})

    def on_selection_modified_async(self, view):
        if len(view.sel()) > 1:
            return
        else:
            view.hide_popup()
            # if self.prev_selection == view.sel():
            #     return
            # else:
            #     view.hide_popup()
            #     self.prev_selection = view.sel()
        try:
            scope_name = view.scope_name(view.sel()[0].b)
            selection = view.substr(view.word(view.sel()[0]))
            line = view.line(view.sel()[0])
            line_contents = view.substr(line).lower()
            popup_label = self.return_label(view, selection)
            doTranslate = False
            if "source.python" in scope_name:
                if "lang" in line_contents or "label" in line_contents or "string" in line_contents:
                    doTranslate = True
                elif popup_label and popup_label > 30000:
                    doTranslate = True
            elif "text.xml" in scope_name:
                if "<label" in line_contents or "<property" in line_contents or "<altlabel" in line_contents or "localize" in line_contents:
                    doTranslate = True
            if doTranslate:
                view.show_popup(popup_label, sublime.COOPERATE_WITH_AUTO_COMPLETE,
                                location=-1, max_width=1000, on_navigate=lambda label_id, view=view: jump_to_label_declaration(view, label_id))
        except:
            log("exception in on_selection_modified_async")

    def on_load_async(self, view):
        self.check_project_change(view)

    def check_project_change(self, view):
        view = sublime.active_window().active_view()
        project_name = view.window().project_file_name()
        if view.window() and project_name and project_name != self.actual_project:
            self.actual_project = project_name
            log("project change detected: " + project_name)
            Infos.update_include_list(view)
            self.update_labels(view)
            return True
        else:
            return False

    def on_activated_async(self, view):
        if view:
            if not self.settings_loaded:
                self.get_settings()
            if not view.window():
                return True
            if not self.labels_loaded:
                self.get_builtin_label()
            self.check_project_change(view)

    def on_post_save_async(self, view):
        Infos.update_include_list(view)

    def return_label(self, view, selection):
        if selection.isdigit():
            id_string = "#" + selection
            if id_string in self.id_list:
                index = self.id_list.index(id_string)
                tooltips = self.string_list[index]
                if self.use_native:
                    tooltips += "<br>" + self.native_string_list[index]
                return tooltips
        return ""

    def get_settings(self):
        history = sublime.load_settings(SETTINGS_FILE)
        self.kodi_path = history.get("kodi_path")
        log("kodi path: " + self.kodi_path)
        self.use_native = history.get("use_native_language")
        if self.use_native:
            self.language_folder = history.get("native_language")
            log("use native language: " + self.language_folder)
        else:
            self.language_folder = DEFAULT_LANGUAGE_FOLDER
            log("use default language: English")
        self.settings_loaded = True

    def get_addon_lang_file(self, path):
        paths = [os.path.join(path, "resources", "language", self.language_folder, "strings.po"),
                 os.path.join(path, "..", "language", self.language_folder, "strings.po")]
        path = checkPaths(paths)
        if path:
            return codecs.open(path, "r", "utf-8").read()
        else:
            log("Could not find addon language file")
            log(paths)
            return ""

    def get_kodi_lang_file(self):
        paths = [os.path.join(self.kodi_path, "addons", "resource.language.en_gb", "resources", "strings.po"),
                 os.path.join(self.kodi_path, "language", self.language_folder, "strings.po")]
        path = checkPaths(paths)
        if path:
            return codecs.open(path, "r", "utf-8").read()
        else:
            log("Could not find kodi language file")
            log(paths)
            return ""

    def get_builtin_label(self):
        kodi_lang_file = self.get_kodi_lang_file()
        if kodi_lang_file:
            po = polib.pofile(kodi_lang_file)
            self.builtin_id_list = []
            self.builtin_string_list = []
            self.builtin_native_string_list = []
            for entry in po:
                self.builtin_id_list.append(entry.msgctxt)
                self.builtin_string_list.append(entry.msgid)
                self.builtin_native_string_list.append(entry.msgstr)
            self.labels_loaded = True
            log("Builtin labels loaded. Amount: %i" % len(self.builtin_string_list))

    def update_labels(self, view):
        if view.file_name():
            self.id_list = self.builtin_id_list
            self.string_list = self.builtin_string_list
            self.native_string_list = self.builtin_native_string_list
            path, filename = os.path.split(view.file_name())
            lang_file = self.get_addon_lang_file(path)
            po = polib.pofile(lang_file)
            log("Update labels for: %s" % path)
            for entry in po:
                self.builtin_id_list.append(entry.msgctxt)
                self.builtin_string_list.append(entry.msgid)
                self.builtin_native_string_list.append(entry.msgstr)
                log("Labels updated. Amount: %i" % len(self.id_list))


class SetKodiFolderCommand(sublime_plugin.WindowCommand):

    def run(self):
        sublime.active_window().show_input_panel("Set Kodi folder", KODI_PRESET_PATH, self.set_kodi_folder, None, None)

    def set_kodi_folder(self, path):
        if os.path.exists(path):
            sublime.load_settings(SETTINGS_FILE).set("kodi_path", path)
            sublime.save_settings(SETTINGS_FILE)
        else:
            sublime.message_dialog("Folder %s does not exist." % path)


class ReloadKodiLanguageFilesCommand(sublime_plugin.WindowCommand):

    def run(self):
        pass


class SearchForLabelCommand(sublime_plugin.WindowCommand):

    def is_visible(self):
        view = self.window.active_view()
        scope_name = view.scope_name(view.sel()[0].b)
        return "source.python" in scope_name or "text.xml" in scope_name

    def run(self):
        pass


class OpenKodiLogCommand(sublime_plugin.WindowCommand):

    def run(self):
        history = sublime.load_settings(SETTINGS_FILE)
        if sublime.platform() == "linux":
            self.log_file = os.path.join(os.path.expanduser("~"), ".%s" % APP_NAME, "temp", "%s.log" % APP_NAME)
        elif sublime.platform() == "windows":
            if history.get("portable_mode"):
                self.log_file = os.path.join(history.get("kodi_path"), "portable_data", "%s.log" % APP_NAME)
            else:
                self.log_file = os.path.join(os.getenv('APPDATA'), "%s" % APP_NAME, "%s.log" % APP_NAME)
        sublime.active_window().open_file(self.log_file)


class OpenSourceFromLog(sublime_plugin.TextCommand):

    def run(self, edit):
        for region in self.view.sel():
            if region.empty():
                line = self.view.line(region)
                line_contents = self.view.substr(line)
                ma = re.search('File "(.*?)", line (\d*), in .*', line_contents)
                if ma:
                    target_filename = ma.group(1)
                    target_line = ma.group(2)
                    sublime.active_window().open_file("%s:%s" % (target_filename, target_line), sublime.ENCODED_POSITION)
                    return
                ma = re.search(r"', \('(.*?)', (\d+), (\d+), ", line_contents)
                if ma:
                    target_filename = ma.group(1)
                    target_line = ma.group(2)
                    target_col = ma.group(3)
                    sublime.active_window().open_file("%s:%s:%s" % (target_filename, target_line, target_col), sublime.ENCODED_POSITION)
                    return
            else:
                self.view.insert(edit, region.begin(), self.view.substr(region))


class PreviewImageCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        path, filename = os.path.split(self.view.file_name())
        region = self.view.sel()[0]
        line = self.view.line(region)
        line_contents = self.view.substr(line)
        scope_name = self.view.scope_name(region.begin())
        if "string.quoted.double.xml" in scope_name:
            scope_area = self.view.extract_scope(region.a)
            rel_image_path = self.view.substr(scope_area).replace('"', '')
        else:
            root = ET.fromstring(line_contents)
            rel_image_path = root.text
        if rel_image_path.startswith("special://skin/"):
            rel_image_path = rel_image_path.replace("special://skin/", "")
            imagepath = os.path.join(path, "..", rel_image_path)
        else:
            imagepath = os.path.join(path, "..", "media", rel_image_path)
        if os.path.exists(imagepath):
            if os.path.isdir(imagepath):
                self.files = []
                for (dirpath, dirnames, filenames) in os.walk(imagepath):
                    self.files.extend(filenames)
                    break
                self.files = [imagepath + s for s in self.files]
            else:
                self.files = [imagepath]
            sublime.active_window().show_quick_panel(self.files, lambda s: self.on_done(s), selected_index=0, on_highlight=lambda s: self.show_preview(s))

    def on_done(self, index):
        sublime.active_window().focus_view(self.view)

    def show_preview(self, index):
        if index >= 0:
            file_path = self.files[index]
            sublime.active_window().open_file(file_path, sublime.TRANSIENT)


class GoToVariableCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        Infos.go_to_tag(view=self.view)


class GoToIncludeCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        Infos.go_to_tag(view=self.view)


class SearchForImageCommand(sublime_plugin.TextCommand):

    def is_visible(self):
        scope_name = self.view.scope_name(self.view.sel()[0].b)
        return "source.python" in scope_name or "text.xml" in scope_name

    def run(self, edit):
        path, filename = os.path.split(self.view.file_name())
        self.imagepath = os.path.join(path, "..", "media")
        # self.pos = self.view.sel()
        if not os.path.exists(self.imagepath):
            log("Could not find file " + self.imagepath)
        self.files = []
        for path, subdirs, files in os.walk(self.imagepath):
            if "studio" in path or "recordlabel" in path:
                continue
            for filename in files:
                image_path = os.path.join(path, filename).replace(self.imagepath, "").replace("\\", "/")
                if image_path.startswith("/"):
                    image_path = image_path[1:]
                self.files.append(image_path)
        sublime.active_window().show_quick_panel(self.files, lambda s: self.on_done(s), selected_index=0, on_highlight=lambda s: self.show_preview(s))

    def on_done(self, index):
        items = ["Insert path", "Open Image"]
        if index >= 0:
            sublime.active_window().show_quick_panel(items, lambda s: self.insert_char(s, index), selected_index=0)
        else:
            sublime.active_window().focus_view(self.view)

    def insert_char(self, index, fileindex):
        if index == 0:
            self.view.run_command("insert", {"characters": self.files[fileindex]})
        elif index == 1:
            os.system("start " + os.path.join(self.imagepath, self.files[fileindex]))
        sublime.active_window().focus_view(self.view)

    def show_preview(self, index):
        if index >= 0:
            file_path = os.path.join(self.imagepath, self.files[index])
        sublime.active_window().open_file(file_path, sublime.TRANSIENT)


class SearchForFontCommand(sublime_plugin.TextCommand):

    def is_visible(self):
        scope_name = self.view.scope_name(self.view.sel()[0].b)
        return "text.xml" in scope_name

    def run(self, edit):
        path, filename = os.path.split(self.view.file_name())
        self.font_file = os.path.join(path, "Font.xml")
        if os.path.exists(self.font_file):
            parser = ET.XMLParser(remove_blank_text=True)
            tree = ET.parse(self.font_file, parser)
            root = tree.getroot()
            self.fonts = []
            for node in root.find("fontset").findall("font"):
                string_array = [node.find("name").text, node.find("size").text + "  -  " + node.find("filename").text]
                self.fonts.append(string_array)
            sublime.active_window().show_quick_panel(self.fonts, lambda s: self.on_done(s), selected_index=0)

    def on_done(self, index):
        if index >= 0:
            self.view.run_command("insert", {"characters": self.fonts[index][0]})
        sublime.active_window().focus_view(self.view)


# def plugin_loaded():
#     view = sublime.active_window().active_view()
#     Infos.update_include_list(view)

