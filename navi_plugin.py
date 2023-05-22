import os, sys
import requests, json
import sublime, sublime_plugin
import re
def navi_to_sublime(navi_command):
    # Fetch active window and view
    window = sublime.active_window()
    view = window.active_view()
    edit = view.begin_edit()

    # Parse the Navi command and extract the action and arguments
    action, *args = navi_command.split(' ')

    # Define action mapping
    actions = {
        'focus-group': lambda: window.focus_group(int(args[0])),
        'focus-view': lambda: window.focus_view(window.views_in_group(window.active_group())[int(args[0])]),
        'view-open': lambda: window.open_file(args[0]),
        'view-close': lambda: window.run_command('close'),
        'insert': lambda: view.insert(edit, view.sel()[0].begin(), ' '.join(args)),
        'insert-line': lambda: view.insert(edit, view.sel()[0].begin(), ' '.join(args) + '\n'),
        'delete': lambda: view.erase(edit, sublime.Region(view.sel()[0].begin(), view.sel()[0].begin() + int(args[0]))),
        'delete-line': lambda: view.erase(edit, view.line(view.sel()[0])),
        'select-all': lambda: view.sel().add(sublime.Region(0, view.size())),
        'select-word': lambda: view.sel().add(view.word(view.sel()[0])),
        'select-line': lambda: view.sel().add(view.line(view.sel()[0])),
        'move-to': lambda: view.sel().add(sublime.Region(view.text_point(int(args[0]), int(args[1])))),
        'find': lambda: view.sel().add(view.find_all(args[0])[0]) if view.find_all(args[0]) else None,
        'copy': lambda: sublime.set_clipboard(view.substr(view.sel()[0])),
        'paste': lambda: view.insert(edit, view.sel()[0].begin(), sublime.get_clipboard()),
        'undo': lambda: view.run_command('undo'),
        'redo': lambda: view.run_command('redo'),
        'replace': lambda: view.run_command('replace_all', {"find": args[0], "replace": args[1]}),
        'save': lambda: view.run_command('save'),
        'rename': lambda: os.rename(args[0], args[1]),
        'create-dir': lambda: os.makedirs(args[0], exist_ok=True),
        'delete-file': lambda: os.remove(args[0]),
        'comment-line': lambda: view.run_command('toggle_comment', {"block": False}),
        'uncomment-line': lambda: view.run_command('toggle_comment', {"block": False}),
        'indent': lambda: view.run_command('indent'),
        'dedent': lambda: view.run_command('dedent')
    }

    # Call the action
    if action in actions:
        actions[action]()
    else:
        print("Action {action} not found".format())

    view.end_edit(edit)

def process_navi_script(navi_script):
  # Split the script into separate commands and execute each one
  for command in navi_script.split('\n'):
      if command:  # Ignore empty commands
          navi_to_sublime(command)

def get_cursors(view):
  return [ 
    (view.rowcol(region.begin())[0], view.rowcol(region.begin())[1])
    for region in view.sel() 
  ]

# Write a function that returns of a string of the context of lines (-k,k) in the view, 
# relative to the cursors in curs. Make sure that the current cursor positions are obvious
# in the returned string.
def grab_text(k, view, curs):
  context_lines = []
  syntax = view.settings().get('syntax').split('/')[-1].split('.')[0].lower()
  for row, col in curs:
    start_line = max(row - k, 0)
    end_line = min(row + k + 1, view.size())  # Ensure not exceeding view size

    lines = []
    for i in range(start_line, end_line):
        line_region = view.line(view.text_point(i, 0))
        txt = view.substr(line_region)
        if i == row:  # If it's the current cursor's line
            # Add a marker at the cursor's column
            if txt:
              txt = "->>> " + ''.join([ ('⟦'+c+'⟧' if j == col else c) for (j,c) in enumerate(txt)])
              # txt[:col] + "((" + txt[] + "))" + txt[col:]
        lines.append(txt)

    # We don't need the current_cursor_marker in this case, as we mark the cursor directly in the text
    context_lines.extend(lines)  # Add the lines to the context
  snippet = "\n".join(context_lines)
  snippet_md = "```{}\n{}\n```".format(syntax, snippet)
  return snippet_md


def view_tree(win): # Create a tree representation of views and their cursor positions
  view_tree = {}
  for group in range(win.num_groups()):
    view_tree[group] = []
    for view in win.views_in_group(group):
      vname = view.file_name() if view.file_name() else "untitled"
      (line,col) = get_cursors(view)[0]
      token = '=>' if view == win.active_view_in_group(group) else ' >' 
      view_str = "{} {}   (line: {}, column: {})".format(token, vname, line, col)
      view_tree[group].append(view_str)
  return view_tree

# 2. I want to add information about the current state of sublime text to my prompts, so that GPT is aware of the text in the document, etc.
#    Write a function that returns a string containing relevant information about the current state of SublimeText.   
def sublime_state():
  window = sublime.active_window()
  aview = window.active_view()
  state_info = ""
  # Construct the state information string
  for group, views in view_tree(window).items():
    state_info += "Views in group {}:\n".format(group)
    for i, view in enumerate(views):
      state_info += "{} {}\n".format(i, view)
  return state_info

# Command for sending prompt to Navi server
class NaviCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        sublime.active_window().show_input_panel("", "", self.on_done, None, None)

    def on_done(self, user_input):
      url = "http://localhost:5000/receive"
      headers = {"Content-Type": "application/json"}
      subl_data = json.dumps(
        { "user_prompt": user_input, "subl_state": sublime_state() }
      )

      response = requests.post(url, headers=headers, data=subl_data, stream=True)
      print(response)
      for chunk in response.iter_content(chunk_size=100*8192, decode_unicode=True):
        print(chunk)