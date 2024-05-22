import time
import os 
import pickle
from collections import OrderedDict
import torch
from options.train_options import TrainOptions
from data.data_loader import CreateDataLoader
from models.models import create_model
from util.visualizer import Visualizer

def save_model(model, epoch, total_steps, label, save_dir):
    save_filename = f'{label}_epoch_{epoch}_steps_{total_steps}.pth'
    save_path = os.path.join(save_dir, save_filename)
    torch.save({
        'epoch': epoch,
        'total_steps': total_steps,
        'model_state_dict': model.state_dict(),
        'optimizer_state_dict': model.optimizer.state_dict(),
    }, save_path)
    print(f'Saved model at {save_path}')

opt = TrainOptions().parse()
data_loader = CreateDataLoader(opt)
dataset = data_loader.load_data()
dataset_size = len(data_loader)
print('#training images = %d' % dataset_size)

model = create_model(opt)
visualizer = Visualizer(opt)

info_dir = os.path.join(opt.checkpoints_dir, opt.name)
os.makedirs(info_dir, exist_ok=True)
infoname = f'{opt.which_epoch}.pkl'
infoname = os.path.join(info_dir, infoname)
if opt.continue_train and os.path.exists(infoname):
    print('Loaded epoch and total_steps')
    with open(infoname, 'rb') as file:
        info = pickle.load(file)
    epoch_count = info['epoch']
    total_steps = info['total_steps']
else:
    epoch_count = opt.epoch_count
    total_steps = 0

print("Start epoch: ", epoch_count)
print("Total steps: ", total_steps)

for steps in range(epoch_count-1):
    for scheduler in model.schedulers:
        scheduler.step()

stat_errors = OrderedDict([('count', 0)])
for epoch in range(epoch_count, opt.niter + opt.niter_decay + 1):
    epoch_start_time = time.time()
    epoch_iter = 0
    for i, data in enumerate(dataset):
        iter_start_time = time.time()
        visualizer.reset()
        total_steps += 1
        epoch_iter += 1
        model.set_input(data)
        model.optimize_parameters()
        
        # stat errors
        current_errors = model.get_current_errors()
        stat_errors['count'] += 1  
        for key in current_errors.keys():
            if key in stat_errors:
                stat_errors[key] += current_errors[key]
            else:
                stat_errors[key] = current_errors[key]
        
        if total_steps % opt.print_freq == 0:
            errors = model.get_current_errors()
            t = time.time() - iter_start_time
            visualizer.print_current_errors(epoch, epoch_iter, errors, t)
        
        # save latest model
        if total_steps % opt.save_latest_freq == 0:
            print('saving the latest model (epoch %d, total_steps %d)' % (epoch, total_steps))
            save_model(model, epoch, total_steps, 'latest', info_dir)
    
    t = time.time() - iter_start_time
    for key in stat_errors.keys():
        if key != 'count':
            stat_errors[key] /= stat_errors['count']
    visualizer.print_current_errors(epoch, epoch_iter, stat_errors, t)
    if opt.display_id > 0:
        visualizer.plot_current_errors(epoch, float(epoch_iter) / dataset_size, opt, stat_errors)
    stat_errors = OrderedDict([('count', 0)])
    
    # save images
    save_result = False
    visualizer.display_current_results(model.get_current_visuals(), epoch, save_result)
    
    # save epoch model
    if epoch % opt.save_epoch_freq == 0:
        print('saving the model at the end of epoch %d, iters %d' % (epoch, total_steps))
        save_model(model, epoch, total_steps, 'epoch', info_dir)
        save_model(model, epoch, total_steps, 'latest', info_dir)
    
    # print time used
    print('End of epoch %d / %d \t Time Taken: %d sec' % (epoch, opt.niter + opt.niter_decay, time.time() - epoch_start_time))
    
    model.update_learning_rate()
    
    # Save training state
    info = {'epoch': epoch + 1, 'total_steps': total_steps}
    with open(infoname, 'wb') as file:
        pickle.dump(info, file)
