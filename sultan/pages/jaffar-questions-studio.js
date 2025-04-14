/******************      INTRO       *****************************************
This page manage all the sultan project.
It is not best practice but at the moment the focus is on portability.
@oswald.bernard@hsbc.com
archi link:
*/


/***********************   INIT    *************************************/

let jaffarConfigLocalDB = new PouchDB("jcDB");                


/***********************   ALPINE    *************************************/

function jaffarQuestionsStudio() {
  return {
     page:'jaffar-questions-studio',
     //     Jaffar config page
     jaffarConfigs:[],
     async init(){
     let jaffarConfigs =  await getLocalConfigJaffar()
     this.jaffarConfigs=jaffarConfigs.questions
     this.$watch("jaffarConfigs", value=>updateLocalDBJaffar(value))
    },

     escalationQuestionConfigsSelectedQuestion:0,
     jaffarConfigsSelectedQuestion:0,
     MoveDownJaffarQuestions(index){
      const currentValueAtTheIndex=this.jaffarConfigs[index] //A
      const futurIndexCurrentValue=this.jaffarConfigs[index-1] //B
      this.jaffarConfigs[index-1]=currentValueAtTheIndex
      this.jaffarConfigs[index]=futurIndexCurrentValue
     },
     MoveUpJaffarQuestions(index){
      const currentValueAtTheIndex=this.jaffarConfigs[index] //A
      const futurIndexCurrentValue=this.jaffarConfigs[index+1] //B
      this.jaffarConfigs[index+1]=currentValueAtTheIndex
      this.jaffarConfigs[index]=futurIndexCurrentValue
     },
     addAQuestionJaffar(){
     let question={}
     question.name=""
     question.template=""
     question.key=""
     question.options=[]
     this.jaffarConfigs.push(question)
     },
      removeAQuestionJaffar(index){
     this.jaffarConfigs.splice(index,1)
     },
     // Jaffar config import page
     importConfig:[],
     async loadConfigJaffar(){
       await deleteLocalDBJaffar()
       jaffarConfigLocalDB = new PouchDB("jcDB");
       await saveLocalDBJaffar(JSON.parse(this.importConfig)["questions"])
       jaffarConfigs =  await getLocalConfigJaffar()
       this.jaffarConfigs = jaffarConfigs.questions
       this.page = 'jaffar-questions-studio'
     },
     // Jaffar config export
     jaffarConfigExport:'',
     prepTheDataForExportJaffar(){
      let exportJaffar={}

      exportJaffar._id="jaffarConfig"

      exportJaffar.questions=this.jaffarConfigs
      console.log(exportJaffar)

      this.jaffarConfigExport = JSON.stringify(exportJaffar)
      console.log(this.jaffarConfigExport)
      return this.page='export-to-jaffar'
     }
  }
}


/***********************   HELPER    *************************************/

// JAFFAR
async function getLocalConfigJaffar() {
  // get the localConfig for jaffar

    try {   let localConfig = await jaffarConfigLocalDB.get("jaffarConfig")
      return localConfig
      } catch {
      return saveLocalDBJaffar([])
      }
  
}

async function saveLocalDBJaffar(value){
 const doc = {};
 doc["_id"]="jaffarConfig";
 doc["questions"] = value;
await jaffarConfigLocalDB.put(doc)
return;
}

async function updateLocalDBJaffar(value){
 let doc = await getLocalConfigJaffar() ;
 doc["questions"] = value;
 await jaffarConfigLocalDB.put(doc)
return;
}


async function deleteLocalDBJaffar() {
  return await jaffarConfigLocalDB.destroy()
}
