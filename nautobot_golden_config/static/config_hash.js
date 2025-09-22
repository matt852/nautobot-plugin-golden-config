const nautobot_crsf_token = "{{ csrf_token }}";

function formatJobData(data) {
  const arrayFields = ["config_hash", "job_queue"];

  const form_data = formDataToDictionary(data, arrayFields);
  delete form_data.csrfmiddlewaretoken;
  delete form_data.q;
  delete form_data.device;
  delete form_data.related_check;
  if (form_data.job_queue) {
    job_queue = form_data.job_queue;
    delete form_data.job_queue;
  }

  data = { data: form_data };
  if (typeof job_queue !== "undefined") {
    data.job_queue = job_queue[0].name;
  }
  console.log(data);
  return data;
}

function isValidURL(url) {
  // Regular expression to validate URLs
  var urlPattern =
    /^(https?:\/\/)?([\w-]+(\.[\w-]+)+|localhost|(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}))(:\d+)?(\/\S*)?$/;
  return urlPattern.test(url);
}

const generatePlanButton = document.getElementsByClassName("hash-plan-generate");
const form = document.querySelector("form:not(#navbar_search)");

generatePlanButton.addEventListener("click", function (event) {
  event.preventDefault(); // Prevent the default behavior of the anchor link
  document.getElementById("jobStatus").innerHTML = "";
  document.getElementById("jobResults").innerHTML = "";
  document.getElementById("redirectLink").innerHTML = "";
  document.getElementById("detailMessages").style.display = "none";
  openModalAndStartJob();
});

form.addEventListener("submit", function (event) {
  event.preventDefault(); // Prevent the form submission
  openModalAndStartJob();
});

const dynamicGroups = [];

function getDynamicGroupsFromCheckAssociations() {
  let config_hash_groupings = document.getElementById(
    "id_config_hash_groupings"
  ).selectedOptions;
  dynamicGroups.length = 0; // Clear the array before populating it
  for (let i = 0; i < config_hash_groupings.length; i++) {
    let hashId = config_hash_groupings[i].value;
    let apiPath = `/api/plugins/golden-config/config-hash-grouping/${hashId}/`;
    console.log(apiPath);
    fetch(apiPath, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": nautobot_crsf_token,
      },
    })
      .then((response) => {
        if (response.ok) {
          return response.json();
        } else {
          throw new Error(
            "Error fetching hash grouping data: " + response.status
          );
        }
      })
      .then((data) => {
        const groupIds = data.device_groups.map((group) => group.id);
        console.log(groupIds);
        dynamic_groups.push(...groupIds);
      })
      .catch((error) => {
        console.error("Error:", error);
      });
  }
}

const redirectUrlTemplate =
  "/plugins/nautobot-operational-compliance/check-compliance/?";

function serializeFormDataToArray(form) {
  const formData = new FormData(form);
  const params = [];
  for (const [key, value] of formData) {
    if (value) {
      // Only include non-empty values
      params.push({ name: key, value: value });
    }
  }

  return params;
}

function openModalAndStartJob() {
  let check_device_associations = document.getElementById(
    "id_check_device_associations"
  ).selectedOptions;
  let job_queue = document.getElementById("id_job_queue").selectedOptions;

  if (!check_device_associations[0].value || !job_queue[0].value) {
    alert("Please select a device association and job queue to compare.");
  } else {
    $("#modalPopup").modal("show");
    startJob(
      "Check Compliance",
      formatJobData(serializeFormDataToArray(form)),
      redirectUrlTemplate
    );
  }
}
