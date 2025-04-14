// ###################################################
//  Javascript controller for the directry studio
// ###################################################

// ######## INIT ################################

let templateLocalDB = new PouchDB("templatesDB");

// ######## ALPINEJS #######################

function jaffarEscalationTemplatesStudio() {
  return {
    page: "template-studio",
    templates: [],
    selectedTemplate: {},
    jaffarConfig: {},
    async init() {
     this.jaffarConfig = await getConfig('jaffarConfig')
      this.templates = (await this.getAlltemplates()) || [];
      this.$watch("selectedTemplate", (value) => this.updateATemplate(value));
      variables = this.jaffarConfig.questions
        .flat()
        .map((x) => ({ login: x.key, name: x.key.toLowerCase() }));

      $("#editor").trumbowyg({
        html: "<p>coucou</p>",
        autogrow: true,
        btns: [
          ["fontfamily"],
          ["fontsize"],
          ["strong", "em"],
          ["foreColor", "backColor"],
          ["mention"],
          ["table"],
          ["tableCellBackgroundColor", "tableBorderColor"],
          ["link"],
        ],
        plugins: {
          mention: {
            source: variables,
            formatDropdownItem: function (item) {
              return item.name;
            },
            formatResult: function (item) {
              return "{{" + item.login + "}}";
            },
          },
          fontfamily: {
            fontList: [
              { name: "Arial", family: "Arial, Helvetica, sans-serif" },
              { name: "Open Sans", family: "'Open Sans', sans-serif" },
            ],
          },
        },
      });
    },
    getAlltemplates: async function () {
      this.templates = [];
      templates = await templateLocalDB.allDocs({ include_docs: true });
      templates.rows.forEach((x) => this.templates.push(x.doc));
      return (this.templates = this.templates.reverse());
    },
    createATemplate: async function () {
      await sessionStorage.removeItem("template");
      this.selectedTemplate = {
        name: "",
        _id: "Template-" + new Date().getTime(),
        type: "email",
        subject: "Change the subject",
        message: ``,
      };
      this.templates.push(this.selectedTemplate);
      createATemplateDB(this.selectedTemplate);
      this.getAlltemplates();
    },
    updateATemplate: async function () {
      rev = await templateLocalDB.get(this.selectedTemplate._id);
      template = { ...this.selectedTemplate };
      template._rev = rev["_rev"];
      await templateLocalDB.put(template);
      return this.getAlltemplates();
    },
    deleteATemplate: async function (id) {
      // call the helper deleteATemplate with as a param this.selectedTemplate._id
      await deleteATemplate(id);
      this.getAlltemplates();
    },
    selectTemplate: function (templateId) {
      this.templates.forEach((x) => {
        if (x._id == templateId) {
          this.selectedTemplate = x;
        }
      });
      $("#editor").html(this.selectedTemplate.message);
    },
    saveMessage: function () {
      template = $("#editor").trumbowyg("html");
      this.selectedTemplate.message = template;
    },
    // Jaffar config export
    jaffarConfigExport: "",
    prepTheDataForExportJaffar() {
      let exportJaffar = {};

      exportJaffar._id = "jaffarEscalationTemplates";

      exportJaffar.templates = this.templates;
      this.jaffarConfigExport =JSON.stringify(exportJaffar);
      this.page = "export-to-jaffar";
    },
    async importTemplates(){
        //erase the localdb
       await templateLocalDB.destroy()
       templateLocalDB = new PouchDB("templatesDB");
       this.templates= await getConfig('jaffarTemplates')
       this.templates = this.templates.templates
       this.templates.forEach(x=>{
        if(x._rev){delete x._rev}
        createATemplateDB(x)}
       )
    }
  };
}

// ############## HELPERS ###########################

async function getConfig(file) {
 env = getEnv()
questions = await axios.get('/pc-analytics-jaffar/jaffar/configs/get?file='+file)
  return questions.data;
}

function getEnv() {
  str = window.location.href;
  return str.includes("stratpy")
    ? str.split("stratpy-")[1].split(".")[0]
    : "localhost";
}

async function createATemplateDB(template) {
  
  return templateLocalDB.put(template);
}


async function deleteATemplate(id) {
  // this function delete the templateId in the pouchDB
  template = await templateLocalDB.get(id);
  await templateLocalDB.remove(template);
  return;
}
