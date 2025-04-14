// ###################################################
//  Javascript controller for the directry studio
// ###################################################

// ######## INIT ################################

let escalationLocalDB = new PouchDB("escalationDB");

// ######## ALPINEJS #######################

function jaffarEscalationDirectoryStudio(){
    return {
        page:"escalation-studio",
        importConfig:[],
        groups:[],
        questions:'',
        selectedGroup:{},
        entities:[],
        locations:[],
        assets:[],
        sites:[{}],
        templates:[],
        keys:[],
        issuesFamilies: [],
        grid:'',
        drawer:-1,
        filter:'',
        get filteredGroups() {
                if (!this.filter) {
                    return this.groups;
                }
                return this.groups.filter(group => group.email && group.email.includes(this.filter));
            },
        saveEntities:function(value){
        if (!this.groups[this.drawer]["entities"]) {
        this.groups[this.drawer]["entities"] = [];
      }
      let index = this.groups[this.drawer]["entities"].indexOf(value);
      index != -1
        ? this.groups[this.drawer]["entities"].splice(index, 1)
        : this.groups[this.drawer]["entities"].push(value);
        },
        saveLocations:function(value){
        if (!this.groups[this.drawer]["locations"]) {
        this.groups[this.drawer]["locations"] = [];
      }
      let index = this.groups[this.drawer]["locations"].indexOf(value);
      index != -1
        ? this.groups[this.drawer]["locations"].splice(index, 1)
        : this.groups[this.drawer]["locations"].push(value);
        },
        confirmDeletion: function(index) {
        if (confirm("Are you sure you want to delete this row?")) {
            this.groups.splice(index, 1);
        }
    },
         extractKeys(obj) {
        let keys = [];
        if (obj.key) keys.push(obj.key);

        // Vérification récursive pour les objets imbriqués
        for (const value of Object.values(obj)) {
            if (typeof value === 'object' && value !== null) {
                keys = keys.concat(this.extractKeys(value));
            }
        }

        return keys;
    },

    populateKeys() {
        this.keys = this.questions.flatMap(item => this.extractKeys(item));
    },
       async init(){
            this.questions = await getConfig("jaffarConfig","questions")
            this.populateKeys()
            this.templates = await getConfig("jaffarTemplates","templates")
            this.templates.push("coco")
            this.entities  = this.questions.filter(x=>x.key=='Entity')[0].options.map(x=>x.name)
            this.entities.sort()
              this.locations  = this.questions.filter(x=>x.key=='Location')[0].options.map(x=>x.name)
            this.locations.sort()
            this.locations = this.questions.filter(x=>x.key=='Location')[0].options.map(x=>x.name)
            this.locations.sort()
            this.issuesFamilies = this.questions.filter(x=>x.key=='family issue')[0].options.map(x=>x.name)
            this.issuesFamilies.sort()
            this.assets = this.questions.filter(x=>x.key=='Asset Class')[0].options.map(x=>x.name)
            this.assets.push('Regonial lead')
            this.assets.push('BFC')
            this.assets.sort()
             try {
                this.groups = await escalationLocalDB.get('escalation');
                this.groups = this.groups.escalation
              } catch (error) {
                this.groups = await this.createLocalDBRules();
              }
            this.$watch("groups", value=>this.updateGroups(value))
           },
        updateGroups: async function(){
                console.log("rules changed")
                rules = await escalationLocalDB.get('escalation')
                rules.escalation = this.groups
                await escalationLocalDB.put(rules)

        },
        createLocalDBRules:async function(){
        console.log("create the escalation db")
            rules={}
            rules._id="escalation"
            rules.escalation=[{}]
            await escalationLocalDB.put(rules)
            return []
        },
         // Jaffar config export
    jaffarConfigExport: "",
    prepTheDataForExportJaffar() {
      let exportJaffar = {};
      exportJaffar._id = "jaffarEscalation";
      exportJaffar.escalation = transformEscalation(this.groups);

      this.jaffarConfigExport = JSON.stringify(exportJaffar);
      this.page = "export-to-jaffar";
    },
    async importCurrentConfig(){
        //erase the localdb
//       await escalationLocalDB.destroy()
//       escalationLocalDB = new PouchDB("escalationDB");
       config =await getConfig("jaffarEscalation","escalation")
       this.importConfig={}
       this.importConfig._id="escalation"
       this.importConfig.escalation=config
       this.importConfig=JSON.stringify(this.importConfig)

//       this.groups.forEach(x=>{
//        if(x._rev){delete x._rev}
//        createAGroupDB(x)}
//       )
    },
    loadConfig:async function(){
        this.groups=JSON.parse(this.importConfig).escalation
        this.page="escalation-studio"
    }
        
    }
}


// ############## HELPERS ###########################

async function getConfig(file,key) {
 data = await axios.get('/pc-analytics-jaffar/jaffar/configs/get?file='+file)
 console.log(key)
  return data.data[key];
}


function transformEscalation(escalation) {
  let result = [];

  for (let i = 0; i < escalation.length; i++) {
    const row = escalation[i];

    for (let j = 0; j < row.triggers.length; j++) {
      const trigger = row.triggers[j];

      const transformedObj = {
        id: "Escalation-" + new Date().getTime(),
        name: row.name + " " + trigger.when,
        when:trigger.when,
        triggers: [
          {
            operator: "AND",
            conditions: [
              {
                key: trigger.comparisonKey,
                operator: trigger.operator,
                compareTo: trigger.value,
              },
              {
                key: "assetClass",
                operator: "equals",
                compareTo: row.assetClass,
              },
              {
                key: "location",
                operator: "equals",
                compareTo: row.locations,
              },
              {
                key: "entities",
                operator: "equals",
                compareTo: row.entities,
              },
            ],
          },
        ],
        actions: [
          {
            type: "sendEmail",
            to: row.email,
            template: trigger.template,
          },
        ],
      };

      result.push(transformedObj);
    }
  }

  return result;
}


