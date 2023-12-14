import torch

from ..builder import BBOX_ASSIGNERS
from ..match_costs import build_match_cost
from ..transforms import bbox_cxcywh_to_xyxy
from .assign_result import AssignResult
from .base_assigner import BaseAssigner

try:
    from scipy.optimize import linear_sum_assignment
except ImportError:
    linear_sum_assignment = None


@BBOX_ASSIGNERS.register_module()
class FixedAssigner(BaseAssigner):
    """Computes one-to-one matching between predictions and ground truth.

    This class computes an assignment between the targets and the predictions
    based on the costs. The costs are weighted sum of three components:
    classification cost, regression L1 cost and regression iou cost. The
    targets don't include the no_object, so generally there are more
    predictions than targets. After the one-to-one matching, the un-matched
    are treated as backgrounds. Thus each query prediction will be assigned
    with `0` or a positive integer indicating the ground truth index:

    - 0: negative sample, no assigned gt
    - positive integer: positive sample, index (1-based) of assigned gt

    Args:
        cls_weight (int | float, optional): The scale factor for classification
            cost. Default 1.0.
        bbox_weight (int | float, optional): The scale factor for regression
            L1 cost. Default 1.0.
        iou_weight (int | float, optional): The scale factor for regression
            iou cost. Default 1.0.
        iou_calculator (dict | optional): The config for the iou calculation.
            Default type `BboxOverlaps2D`.
        iou_mode (str | optional): "iou" (intersection over union), "iof"
                (intersection over foreground), or "giou" (generalized
                intersection over union). Default "giou".
    """

    def __init__(self,
                 cls_cost=dict(type='ClassificationCost', weight=1.),
                 reg_cost=dict(type='BBoxL1Cost', weight=1.0),
                 iou_cost=dict(type='IoUCost', iou_mode='giou', weight=1.0)):
        self.cls_cost = build_match_cost(cls_cost)
        self.reg_cost = build_match_cost(reg_cost)
        self.iou_cost = build_match_cost(iou_cost)

    def assign(self,
               bbox_pred,
               cls_pred,
               gt_bboxes,
               gt_labels,
               img_meta,
               gt_bboxes_ignore=None,
               gt_ids=None,
               eps=1e-7):
        """Computes one-to-one matching based on the weighted costs.

        This method assign each query prediction to a ground truth or
        background. The `assigned_gt_inds` with -1 means don't care,
        0 means negative sample, and positive number is the index (1-based)
        of assigned gt.
        The assignment is done in the following steps, the order matters.

        1. assign every prediction to -1
        2. compute the weighted costs
        3. do Hungarian matching on CPU based on the costs
        4. assign all to 0 (background) first, then for each matched pair
           between predictions and gts, treat this prediction as foreground
           and assign the corresponding gt index (plus 1) to it.

        Args:
            bbox_pred (Tensor): Predicted boxes with normalized coordinates
                (cx, cy, w, h), which are all in range [0, 1]. Shape
                [num_query, 4].
            cls_pred (Tensor): Predicted classification logits, shape
                [num_query, num_class].
            gt_bboxes (Tensor): Ground truth boxes with unnormalized
                coordinates (x1, y1, x2, y2). Shape [num_gt, 4].
            gt_labels (Tensor): Label of `gt_bboxes`, shape (num_gt,).
            img_meta (dict): Meta information for current image.
            gt_bboxes_ignore (Tensor, optional): Ground truth bboxes that are
                labelled as `ignored`. Default None.
            eps (int | float, optional): A value added to the denominator for
                numerical stability. Default 1e-7.

        Returns:
            :obj:`AssignResult`: The assigned result.
        """
        assert gt_bboxes_ignore is None, \
            'Only case when gt_bboxes_ignore is None is supported.'
        clip_length = len(bbox_pred)
        total_gt_ids = torch.unique(torch.cat(gt_ids))
        num_gts = total_gt_ids.numel()

        num_bboxes = bbox_pred[0].size(0)

        # 1. assign -1 by default
        assigned_gt_inds = bbox_pred[0].new_full((num_bboxes, ),
                                                 -1,
                                                 dtype=torch.long)
        assigned_labels = bbox_pred[0].new_full((num_bboxes, ),
                                                -1,
                                                dtype=torch.long)
        if num_gts == 0 or num_bboxes == 0:
            # No ground truth or boxes, return empty assignment
            if num_gts == 0:
                # No ground truth, assign all to background
                assigned_gt_inds[:] = 0
            return [
                AssignResult(
                    num_gts, assigned_gt_inds, None, labels=assigned_labels)
                for _ in range(clip_length)
            ]
        img_h, img_w, _ = img_meta['img_shape']
        factor = gt_bboxes[0].new_tensor([img_w, img_h, img_w,
                                          img_h]).unsqueeze(0)
        # past_len = gt_bboxes[0].shape[0]
        # for j in range(0,len(gt_bboxes)):
        #     cur_len = gt_bboxes[j].shape[0]
        #     if cur_len != past_len:
        #         print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        #         print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')

        # 2. compute the weighted costs
        # classification and bboxcost.
        costs = []
        for i in range(clip_length): # 这个循环是对每一帧来说的,gt_labels每一帧都有，理论上应该可以满足帧间gt数量不一样的需求吧,gt_bbox应该也是
            cls_cost = self.cls_cost(cls_pred[i], gt_labels[i])
            # regression L1 cost
            normalize_gt_bboxes = gt_bboxes[i] / factor     # gt现在的形式是xyxy,除以图像分辨率进行归一化
            reg_cost = self.reg_cost(bbox_pred[i], normalize_gt_bboxes)
            # regression iou cost, defaultly giou is used in official DETR.
            bboxes = bbox_cxcywh_to_xyxy(bbox_pred[i]) * factor
            iou_cost = self.iou_cost(bboxes, gt_bboxes[i])
            # weighted sum of above three costs
            cost = cls_cost + reg_cost + iou_cost
            costs.append(cost)
        # cost 一共clip_num个元素，每个元素tensor（proposal_num*gt_num）个

        # 3. build bi-directional one-to-one correspondance
        ims_to_total, ims_to_total_weights, totals_to_ims = [], [], []
        total_gt_ids_list = total_gt_ids.tolist()
        for gt_id in gt_ids:    # 这是在对每帧进行循环，取出当前帧的gt_id
            per_ims_to_total = []
            per_ims_to_total_weights = []
            totals_to_per_ims = []

            for gid in total_gt_ids_list: # 遍历total_gt_ids_list
                if gid in gt_id.tolist():
                    per_ims_to_total.append(gt_id.tolist().index(gid))
                    per_ims_to_total_weights.append(1.)
                    totals_to_per_ims.append(gt_id.tolist().index(gid))
                else: # 如果当前帧某个id缺失，则这个id在该帧下的匹配cost weight为0
                    per_ims_to_total.append(-1)
                    per_ims_to_total_weights.append(0.)
            per_ims_to_total = gt_id.new_tensor(
                per_ims_to_total, dtype=torch.int64) # list转tensor
            per_ims_to_total_weights = gt_id.new_tensor(
                per_ims_to_total_weights, dtype=torch.float32)
            ims_to_total.append(per_ims_to_total)
            ims_to_total_weights.append(per_ims_to_total_weights)

            totals_to_per_ims = gt_id.new_zeros(num_gts + 1, dtype=torch.int64) # clip内总gt数+1，第一维应该是当none-object,后面的维数是真gt
            totals_to_per_ims[1:] = per_ims_to_total + 1 # 第一维是none-object所以切片，后面的等于当前帧的per_ims_to_total+1，因为如果当前帧有个instance没有，则对应的位置为-1+1=0
            totals_to_ims.append(totals_to_per_ims)

        costs_ = [
            cost[:, indices] * weights
            for (cost, indices,
                 weights) in zip(costs, ims_to_total, ims_to_total_weights)
        ] # 这个广播机制挺巧妙的，没有某id_gt的那一帧，100个proposal对他的cost都设置为0，而且id的顺序也是对得上的
        cost = sum(costs_) / sum(ims_to_total_weights) # 把各帧的匹配结果求和，就得到了100个query across每一帧的综合cost,这个代码应该需要假设t帧的instance都出现吧,并不是，上面那个循环估计做了补充措施

        # 4. do Hungarian matching on CPU using linear_sum_assignment
        cost = cost.detach().cpu()
        if linear_sum_assignment is None:
            raise ImportError('Please run "pip install scipy" '
                              'to install scipy first.')
        matched_row_inds, matched_col_inds = linear_sum_assignment(cost) # 返回row_inds是被选中的proposal的序号吧，col_inds是被选中的proposal匹配到的gt的序号吧
        matched_row_inds = torch.from_numpy(matched_row_inds).to(
            bbox_pred[0].device)
        matched_col_inds = torch.from_numpy(matched_col_inds).to(
            bbox_pred[0].device)  # 上面这两句就是把numpy转成tensor

        # 5. assign backgrounds and foregrounds
        # assign all indices to backgrounds first
        assign_results = []
        for _ in range(clip_length):    # 对每一帧进行遍历
            assigned_gt_inds = bbox_pred[0].new_full((num_bboxes, ),
                                                     0,
                                                     dtype=torch.long)  # shape为num_proposal,意为每个proposal给匹配的gt inds,现在先初始化都为0
            assigned_labels = bbox_pred[0].new_full((num_bboxes, ),
                                                    -1,
                                                    dtype=torch.long)   # shape为num_proposal,意为每个proposal匹配的label,现在先初始化都为-1
            # assign foregrounds based on matching results
            matched_col_inds_per_im = totals_to_ims[_][matched_col_inds + 1]    # 总体上，0应该代表none-object,1即以上代表不同的tg object, 这里matched_col_inds+1了，原始的它0也是一个gt,现在加1后0就不是了，现在把0当做none object
            matched_row_inds_per_im = matched_row_inds[
                matched_col_inds_per_im > 0]
            matched_col_inds_per_im = matched_col_inds_per_im[
                matched_col_inds_per_im > 0]
            assigned_gt_inds[matched_row_inds_per_im] = matched_col_inds_per_im #现在给每个proposal写入真正匹配到的的gt inds,0是none-object,非0是真匹配到了gt
            assigned_labels[matched_row_inds_per_im] = gt_labels[_][
                matched_col_inds_per_im - 1]    # 现在给每个proposal写入匹配的到的gt的label,对于一类来说，就是0，其余的none-object的label是-1
            assign_results.append(
                AssignResult(
                    gt_ids[_].numel(),
                    assigned_gt_inds,
                    None,
                    labels=assigned_labels))
        return assign_results
