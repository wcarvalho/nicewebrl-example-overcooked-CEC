import aiofiles
import os.path
import asyncio
from nicegui import app, ui
import zipfile

# from gcs import save_to_gcs_with_retries
import nicewebrl
from nicewebrl.logging import get_logger
from nicewebrl.utils import write_msgpack_record
import sys

logger = get_logger(__name__)

experiment_name = sys.argv[1]
if experiment_name == "coord_ring":
  experiment_file = "coord_ring_experiment.py"
elif experiment_name == "counter_circuit":
  experiment_file = "counter_circuit_experiment.py"
else:
  print("Invalid experiment name")
  sys.exit(1)

NAME = os.environ.get("NAME", experiment_name)
DEBUG = int(os.environ.get("DEBUG", 0))

def download_models_if_needed():
  """Download and extract models.zip if models directory doesn't exist"""
  import requests

  models_dir = "models"
  models_zip = "models.zip"

  if os.path.exists(models_dir):
    return

  print("Models directory not found. Downloading models.zip...")

  # Download the file
  dropbox_url = "https://www.dropbox.com/scl/fi/a5bazgpl4hpsnz2pwmqae/models.zip?rlkey=n8fl1a4xebqc45cf97uv019oq&dl=1"

  response = requests.get(dropbox_url, stream=True)
  if response.status_code == 200:
    with open(models_zip, 'wb') as f:
      for chunk in response.iter_content(chunk_size=8192):
        f.write(chunk)
    print("Downloaded models.zip successfully")
  else:
    raise Exception(
        f"Failed to download models.zip: HTTP {response.status_code}")

  # Extract the zip file
  with zipfile.ZipFile(models_zip, 'r') as zip_ref:
    zip_ref.extractall('.')

  # Clean up the zip file
  os.remove(models_zip)
  print("Extracted models.zip and cleaned up")

download_models_if_needed()


async def save_data(final_save=True, feedback=None, **kwargs):
  user_data_file = nicewebrl.user_data_file()

  if final_save:
    # --------------------------------
    # save user data to final line of file
    # --------------------------------
    user_storage = nicewebrl.make_serializable(dict(app.storage.user))
    last_line = dict(
        finished=True,
        feedback=feedback,
        user_storage=user_storage,
        **kwargs,
    )
    async with aiofiles.open(user_data_file, "ab") as f:  # Changed to binary mode
      await write_msgpack_record(f, last_line)



async def make_consent_form(container):
  consent_given = asyncio.Event()
  with container:
    ui.markdown("## Consent Form")
    with open("consent.md", "r") as consent_file:
      consent_text = consent_file.read()
    ui.markdown(consent_text)
    ui.checkbox("I agree to participate.",
                on_change=lambda: consent_given.set())

  await consent_given.wait()


async def collect_demographic_info(container):
  # Create a markdown title for the section
  nicewebrl.clear_element(container)
  with container:
    ui.markdown("## Demographic Info")
    ui.markdown("Please fill out the following information.")

    with ui.column():
      with ui.column():
        ui.label("Biological Sex")
        sex_input = ui.radio(["Male", "Female"], value="Male").props("inline")

      # Collect age with a textbox input
      age_input = ui.input("Age")

    # Button to submit and store the data
    async def submit():
      age = age_input.value
      sex = sex_input.value

      # Validation for age input
      if not age.isdigit() or not (0 < int(age) < 100):
        ui.notify("Please enter a valid age between 1 and 99.", type="warning")
        return
      app.storage.user["age"] = int(age)
      app.storage.user["sex"] = sex
      logger.info(f"age: {int(age)}, sex: {sex}")

    button = ui.button("Submit", on_click=submit)
    await button.clicked()


async def on_startup(stage_container):
  """Called when experiment starts - UI is available"""
  if not app.storage.user.get("experiment_started", False):
    await make_consent_form(stage_container)
    await collect_demographic_info(stage_container)
    app.storage.user["experiment_started"] = True

async def finish_experiment(meta_container, stage_container):
  nicewebrl.clear_element(meta_container)
  nicewebrl.clear_element(stage_container)
  logger.info("Finishing experiment")
  experiment_finished = app.storage.user.get("experiment_finished", False)

  if experiment_finished and not DEBUG:
    # in case called multiple times
    return

  #########################
  # Save data
  #########################
  async def submit(feedback):
    app.storage.user["experiment_finished"] = True
    with meta_container:
      nicewebrl.clear_element(meta_container)
      ui.markdown(f"## Saving data. Please wait")
      ui.markdown(
          "**Once the data is uploaded, this app will automatically move to the next screen**"
      )

    # when over, delete user data.
    await save_data(final_save=True, feedback=feedback)
    app.storage.user["data_saved"] = True
    print("data saved")

  app.storage.user["data_saved"] = app.storage.user.get("data_saved", False)
  if not app.storage.user["data_saved"]:
    with meta_container:
      nicewebrl.clear_element(meta_container)
      ui.markdown(
          "Please provide feedback on the experiment here. For example, please describe if anything went wrong or if you have any suggestions for the experiment."
      )
      text = ui.textarea().style("width: 80%;")  # Set width to 80% of the container
      button = ui.button("Submit")
      await button.clicked()
      await submit(text.value)

  #########################
  # Final screen
  #########################
  with meta_container:
    nicewebrl.clear_element(meta_container)

    ui.markdown("# Experiment over")
    ui.markdown("## Data saved")
    ui.markdown(
        "### Please record the following code which you will need to provide for compensation"
    )
    ui.markdown(f"### socialrl.cook")
    ui.markdown("#### You may close the browser")


nicewebrl.run(
    storage_secret="a_very_secret_key_for_testing_only_12345",
    experiment_file=experiment_file,
    title="Overcooked CEC Experiment",
    reload=False,
    on_startup_fn=on_startup,
    on_termination_fn=finish_experiment,
)
