import os
import subprocess
import distutils.spawn
from mailbagit.derivative import Derivative
from mailbagit.loggerx import get_logger
import mailbagit.helper.derivative as derivative
import mailbagit.helper.common as common
from bs4 import BeautifulSoup


skip_registry = False

try:
    chromes = ["google-chrome", "chrome.exe", "chrome"]
    chrome = next((c for c in chromes if distutils.spawn.find_executable(c)), None)
    skip_registry = True if chrome is None else False

except:
    skip_registry = True

log = get_logger()

if not skip_registry:

    class PDFChromeDerivative(Derivative):
        derivative_name = "pdf-chrome"
        derivative_format = "pdf"
        derivative_agent = "chrome"
        derivative_agent_version = "unknown"

        def __init__(self, email_account, args, mailbag_dir):
            log.debug(f"Setup {self.derivative_name} derivatives")

            # Sets up self.format_subdirectory
            super().__init__(args, mailbag_dir)

        def do_task_per_account(self):
            print(self.account.account_data())

        def do_task_per_message(self, message):
            errors = []
            try:

                out_dir = os.path.join(self.format_subdirectory, message.Derivatives_Path)
                filename = os.path.join(out_dir, str(message.Mailbag_Message_ID))
                errors = common.check_path_length(out_dir, errors)
                html_name = filename + ".html"
                pdf_name = filename + ".pdf"
                errors = common.check_path_length(pdf_name, errors)

                if message.HTML_Body is None and message.Text_Body is None:
                    log.warn("No HTML or plain text body for " + str(message.Mailbag_Message_ID) + ". No PDF derivative will be created.")
                else:
                    log.debug("Writing HTML to " + str(html_name) + " and converting to " + str(pdf_name))
                    # Calling helper function to get formatted html
                    try:
                        html_formatted, encoding = derivative.htmlFormatting(message, self.args.css)
                    except Exception as e:
                        desc = "Error formatting HTML for PDF derivative"
                        errors = common.handle_error(errors, e, desc)

                    try: 
                        # Modify the HTML so that the PDF prints to a single page
                        # The CSS and JavaScript below is adapted from SDW on stackoverflow
                        # https://stackoverflow.com/a/52128129
                                               
                        # Parse HTML
                        soup = BeautifulSoup(html_formatted, "html.parser")

                        # Add a <style> tag to ensure <html> and <body> take up all available space
                        body_style = soup.new_tag("style")
                        body_style.string = """
                            html, body {
                                    width:  fit-content;
                                    height: fit-content;
                                    margin:  0px;
                                    padding: 0px;
                                }
                        """
                        soup.head.append(body_style)

                        # Add a <style> tag to set arbitrary starting page size
                        # (A JS <script> tag will modify the page size after render)
                        page_style = soup.new_tag("style", id="page_style")
                        page_style.string = "@page { size: 1000px 1000px ; margin : 0px }"
                        soup.head.append(page_style)


                        # Add a <script> tag containing the JS to modify the page size after render
                        script = """
                                function fixpage() {
                                    // Get the height of rendered page in pixels
                                    const renderBlock = document.getElementsByTagName("html")[0];
                                    const renderBlockInfo = window.getComputedStyle(renderBlock)
                                
                                    // fix chrome page sizing bug
                                    const fixHeight = parseInt(renderBlockInfo.height) + 1 + "px"   

                                    // Change CSS in <head> so that printing page size is set to render size
                                    const pageCss = `@page { size: ${renderBlockInfo.width} ${fixHeight} ; margin:0;}`;
                                    document.getElementById("page_style").innerHTML = pageCss;
                                }
                                window.onload = fixpage;
                            """
                        script_tag = soup.new_tag("script")
                        script_tag.string = script
                        soup.body.append(script_tag)
                        
                        # Turn the parsed HTML tree back into a string
                        html_formatted = soup.prettify(encoding).decode(encoding)
                        

                    except Exception as e:
                        desc = "Error when modifying HTML to print without pagebreaks"
                        errors = common.handle_error(errors, e, desc)

                    if not self.args.dry_run:
                        try:
                            if not os.path.isdir(out_dir):
                                os.makedirs(out_dir)

                            with open(html_name, "w", encoding="utf-8") as write_html:
                                write_html.write(html_formatted)
                                write_html.close()
                            command = [
                                chrome,
                                "--headless",
                                "--run-all-compositor-stages-before-draw",
                                "--disable-gpu",
                                "--no-pdf-header-footer",
                                "--print-to-pdf=" + os.path.abspath(pdf_name),
                                os.path.abspath(html_name),
                            ]

                            # Adds --no-sandbox arg to run as root in docker container if env variable set
                            if os.environ.get("IN_CONTAINER", "").upper() == "TRUE":
                                command.insert(4, "--no-sandbox")

                            log.debug("Running " + " ".join(command))
                            p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                            stdout, stderr = p.communicate()
                            if p.returncode == 0:
                                log.debug("Successfully created " + str(message.Mailbag_Message_ID) + ".pdf")
                            else:
                                if stdout:
                                    log.warn("Output converting to " + str(message.Mailbag_Message_ID) + ".pdf: " + str(stdout))
                                if stderr:
                                    desc = "Error converting to " + str(message.Mailbag_Message_ID) + ".pdf: " + str(stderr)
                                    errors = common.handle_error(errors, None, desc, "error")
                            # delete the HTML file
                            if os.path.isfile(pdf_name):
                                os.remove(html_name)

                        except Exception as e:
                            desc = "Error writing HTML and converting to PDF derivative"
                            errors = common.handle_error(errors, e, desc)

            except Exception as e:
                desc = "Error creating PDF derivative with chrome"
                errors = common.handle_error(errors, e, desc)

            message.Errors.extend(errors)

            return message
