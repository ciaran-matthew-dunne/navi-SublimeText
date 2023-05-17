import os, sys
import sublime, sublime_plugin
import re
sys.path.append('/home/ciaran/prog')
import navi


# Okay. Our main Navi python program needs to be running in Python 3.10 to access OpenAI and tinyGPT.
# The plugin will just communicate between ST4 and Navi.
# (e.g., bundles of code sent to ST4 for execution, state passed to Navi-GPT REPL, stdout in repl.) 

def navi_to_sublime(navi_command):
  active_view = sublime.active_window().active_view()

  if navi_command.startswith("view-next"):
      sublime.active_window().run_command('next_view')

  elif navi_command.startswith("view-prev"):
      sublime.active_window().run_command('prev_view')

  elif navi_command.startswith("view-goto"):
      # Note: Sublime Text API does not have a direct goto_view command
      pass

  elif navi_command.startswith("view-close"):
      active_view.run_command('close')

  elif navi_command.startswith("tab-new"):
      sublime.active_window().run_command('new_file')

  elif navi_command.startswith("tab-close"):
      active_view.run_command('close')

  elif navi_command.startswith("insert"):
      text = navi_command.split(' ', 1)[1]
      active_view.run_command('insert', {'characters': text})

  elif navi_command.startswith("delete"):
      num_chars = int(navi_command.split(' ')[1])
      active_view.run_command('left_delete')

  elif navi_command.startswith("delete-line"):
      active_view.run_command('delete_line')

  elif navi_command.startswith("select-all"):
      active_view.run_command('select_all')

  elif navi_command.startswith("select-word"):
      active_view.run_command('expand_selection', {'to': 'word'})

  elif navi_command.startswith("select-line"):
      active_view.run_command('expand_selection', {'to': 'line'})

  elif navi_command.startswith("move-to"):
      row, col = map(int, navi_command.split(' ')[1:])
      pt = active_view.text_point(row - 1, col)
      active_view.sel().clear()
      active_view.sel().add(sublime.Region(pt))

  elif navi_command.startswith("find"):
      pattern = navi_command.split(' ', 1)[1]
      active_view.window().run_command('show_panel', {"panel": "find", "reverse": False})
      active_view.window().run_command('insert', {"characters": pattern})
      active_view.window().run_command('find_next')

  elif navi_command.startswith("scroll-up"):
      active_view.run_command('scroll_lines', {'amount': int(navi_command.split(' ')[1])})

  elif navi_command.startswith("scroll-down"):
      active_view.run_command('scroll_lines', {'amount': -int(navi_command.split(' ')[1])})

# 1b. Write a function that streams the incoming Navi script from GPT to executions of the corresponding SublimeText python code.  
def process_navi_script(navi_script):
  for command in navi_script.split('\n'):
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
      view_str = ""
      vname = view.file_name() if view.file_name() else "Untitled"
      ## Add cursor(s)
      curs = get_cursors(view)
      curs = (curs[0] if len(curs) == 1 else curs)
      view_str = "{} : {}".format(vname, curs)
      if view == win.active_view():
        preview = grab_text(10, view, get_cursors(view))
        view_str = "=> {}\n{}".format(view_str,preview)
      else:
        view_str = "- {}".format(view_str)
      view_tree[group].append(view_str)
  return view_tree

# 2. I want to add information about the current state of sublime text to my prompts, so that GPT is aware of the text in the document, etc.
#    Write a function that returns a string containing relevant information about the current state of SublimeText.   
def sublime_state():
  window = sublime.active_window()
  aview = window.active_view()
  current_file = aview.file_name() if window.active_view() else "Untitled"
  state_info = ""
  # Construct the state information string
  for group, views in view_tree(window).items():
    state_info += "Group {}:\n".format(group)
    for view in views:
      state_info += "{}\n".format(view)
  return "*------ SUBLIME TEXT STATE --------*\n{}\n*----------------------------------*".format(state_info)




# Command for sending prompt to Navi server 
class NaviCommand(sublime_plugin.TextCommand):
  def run(self, edit):
    sublime.active_window().show_input_panel("", "", self.on_done, None, None)

  def on_done(self, user_input):
    txt = re.sub(pattern=r"\\",repl=r"\\\\", string=user_input)
    code = r'prompt = """{}"""'.format(txt)
    win = self.view.window()

    win.run_command('repl_send', 
      {"external_id": 'python', 
       "text": f'chat_sys(navi_gpt_config, """{sublime_state()}""")'})
    win.run_command('repl_send', 
      {"external_id": 'python',
       "text": f'eng_to_navi("""{user_input}""")'})

